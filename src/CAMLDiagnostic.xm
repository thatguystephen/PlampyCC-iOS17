// CAML phase-one observer-only diagnostic for iOS 17.
// This module never replaces a package description, glyph state, argument, or return value.
#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>
#import <rootless.h>
#import <mach-o/loader.h>
#import <dlfcn.h>
#import <os/lock.h>
#import <sys/stat.h>
#import <mach/mach_time.h>
#include <atomic>
#include <stdio.h>
#include <string.h>

static NSString * const kDiagnosticPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kDiagnosticPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";
static NSString * const kDiagnosticEnabledKey = @"kDiagnosticEnabled";
static NSString * const kDiagnosticVerboseKey = @"kDiagnosticVerbose";
static const char * const kDiagnosticBuildId = "plampycc-caml-observer-v1";

static constexpr size_t kRingCapacity = 512;
static constexpr size_t kSerializedEventCapacity = 256;
static constexpr uint64_t kRepeatCollapseWindowMs = 100;
static constexpr uint64_t kTupleDedupWindowMs = 1000;
static constexpr uint64_t kSessionEventCap = 2000;

static std::atomic<bool> gDiagnosticEnabled(false);
static std::atomic<bool> gDiagnosticVerbose(false);
static std::atomic<bool> gLoggingDisabled(false);
static std::atomic<uint64_t> gSessionEventCount(0);
static __thread bool gInDiagnosticObserver = false;
static os_unfair_lock gDiagnosticLock = OS_UNFAIR_LOCK_INIT;
static char gDiagnosticUUID[37] = "unknown";

struct CAMLDiagnosticEvent {
    uint64_t monotonicMs;
    uint64_t wallSeconds;
    char site[16];
    char packageName[48];
    char pathPrefix[16];
    char state[32];
    char descriptionClass[40];
    char ancestorClass[40];
    int32_t viewTag;
    bool descriptionIsNew;
    bool installationRecord;
    uint32_t repeat;
    char serialized[kSerializedEventCapacity];
};

struct CAMLSeenDescription {
    const void *view;
    const void *description;
};

static CAMLDiagnosticEvent gRing[kRingCapacity];
static uint32_t gRingCount = 0;
static CAMLSeenDescription gSeenDescriptions[128] = {};
static uint32_t gSeenDescriptionCount = 0;
static char gLastTuple[128] = {};
static char gLastPair[96] = {};
static uint64_t gLastTupleMs = 0;
static uint64_t gLastPairMs = 0;
static uint32_t gLastRingIndex = 0;

static IMP gOriginalButtonPackage = NULL;
static IMP gOriginalRoundPackage = NULL;
static IMP gOriginalSliderPackage = NULL;
static IMP gOriginalFactory = NULL;
static IMP gOriginalButtonState = NULL;
static IMP gOriginalSliderState = NULL;

static uint64_t DiagnosticMonotonicMilliseconds(void) {
    static mach_timebase_info_data_t timebase = {};
    if (timebase.denom == 0) mach_timebase_info(&timebase);
    uint64_t nanos = mach_absolute_time() * timebase.numer / timebase.denom;
    return nanos / 1000000ULL;
}

static void CopySafe(char *destination, size_t capacity, NSString *value) {
    if (capacity == 0) return;
    destination[0] = '\0';
    if (!value) return;
    const char *source = [value UTF8String];
    if (!source) return;
    size_t out = 0;
    for (size_t i = 0; source[i] != '\0' && out + 1 < capacity; ++i) {
        unsigned char c = (unsigned char)source[i];
        destination[out++] = ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                              (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.') ? (char)c : '_';
    }
    destination[out] = '\0';
}

static void CopySafeCString(char *destination, size_t capacity, const char *value) {
    if (capacity == 0) return;
    destination[0] = '\0';
    if (!value) return;
    size_t out = 0;
    for (size_t i = 0; value[i] != '\0' && out + 1 < capacity; ++i) {
        unsigned char c = (unsigned char)value[i];
        destination[out++] = ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                              (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.') ? (char)c : '_';
    }
    destination[out] = '\0';
}

// Runtime encodings may quote class annotations. The ABI shape is authoritative.
static bool ABIShapeMatches(const char *runtimeEncoding, const char *expectedEncoding) {
    if (!runtimeEncoding || !expectedEncoding) return false;
    char normalized[96] = {};
    size_t out = 0;
    for (size_t i = 0; runtimeEncoding[i] != '\0' && out + 1 < sizeof(normalized); ++i) {
        if (runtimeEncoding[i] == '@' && runtimeEncoding[i + 1] == '"') {
            normalized[out++] = '@';
            i += 2;
            while (runtimeEncoding[i] != '\0' && runtimeEncoding[i] != '"') ++i;
            continue;
        }
        normalized[out++] = runtimeEncoding[i];
    }
    normalized[out] = '\0';
    return strcmp(normalized, expectedEncoding) == 0;
}

static void DiagnosticUUID(void) {
    Dl_info imageInfo = {};
    if (dladdr((const void *)&DiagnosticUUID, &imageInfo) == 0 || !imageInfo.dli_fbase) return;
    const struct mach_header_64 *header = (const struct mach_header_64 *)imageInfo.dli_fbase;
    if (header->magic != MH_MAGIC_64) return;
    const uint8_t *commandBytes = (const uint8_t *)header + sizeof(struct mach_header_64);
    for (uint32_t i = 0; i < header->ncmds; ++i) {
        const struct load_command *command = (const struct load_command *)commandBytes;
        if (command->cmd == LC_UUID && command->cmdsize >= sizeof(struct uuid_command)) {
            const struct uuid_command *uuid = (const struct uuid_command *)commandBytes;
            snprintf(gDiagnosticUUID, sizeof(gDiagnosticUUID),
                     "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
                     uuid->uuid[0], uuid->uuid[1], uuid->uuid[2], uuid->uuid[3],
                     uuid->uuid[4], uuid->uuid[5], uuid->uuid[6], uuid->uuid[7],
                     uuid->uuid[8], uuid->uuid[9], uuid->uuid[10], uuid->uuid[11],
                     uuid->uuid[12], uuid->uuid[13], uuid->uuid[14], uuid->uuid[15]);
            return;
        }
        if (command->cmdsize < sizeof(struct load_command)) return;
        commandBytes += command->cmdsize;
    }
}

static NSString *DiagnosticOutputDirectory(void) {
    return ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic");
}

static bool EnsureDiagnosticOutputFile(NSFileHandle **handle) {
    NSString *directory = DiagnosticOutputDirectory();
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSDictionary *directoryAttributes = @{ NSFilePosixPermissions: @0700 };
    if (![fileManager createDirectoryAtPath:directory withIntermediateDirectories:YES attributes:directoryAttributes error:NULL]) {
        if (![fileManager fileExistsAtPath:directory]) return false;
    }
    NSString *path = [directory stringByAppendingPathComponent:@"events.jsonl"];
    if (![fileManager fileExistsAtPath:path] && ![fileManager createFileAtPath:path contents:nil attributes:@{ NSFilePosixPermissions: @0600 }]) return false;
    chmod(path.fileSystemRepresentation, 0600);
    *handle = [NSFileHandle fileHandleForWritingAtPath:path];
    if (!*handle) return false;
    [*handle seekToEndOfFile];
    return true;
}

static bool SerializeEvent(CAMLDiagnosticEvent *event) {
    const char *buildId = event->installationRecord ? kDiagnosticBuildId : "";
    const char *uuid = event->installationRecord ? gDiagnosticUUID : "";
    // Keep the wire form below 256 bytes even when every bounded field is full.
    uint64_t serializedMonotonic = event->monotonicMs % 10000000000000ULL;
    uint32_t serializedWall = event->wallSeconds > UINT32_MAX ? UINT32_MAX : (uint32_t)event->wallSeconds;
    int written = snprintf(event->serialized, sizeof(event->serialized),
                           "{\"v\":1,\"t\":%llu,\"w\":%u,\"s\":\"%.12s\",\"p\":\"%.20s\",\"x\":\"%.12s\",\"n\":%d,\"g\":\"%.12s\",\"d\":\"%.20s\",\"i\":%d,\"a\":\"%.20s\",\"r\":%u,\"b\":\"%.24s\",\"u\":\"%.36s\"}\n",
                           (unsigned long long)serializedMonotonic, serializedWall,
                           event->site, event->packageName, event->pathPrefix,
                           event->descriptionIsNew ? 1 : 0, event->state,
                           event->descriptionClass, event->viewTag, event->ancestorClass,
                           event->repeat, buildId, uuid);
    return written > 0 && (size_t)written < sizeof(event->serialized);
}

static bool FlushRingLocked(void) {
    if (gRingCount == 0) return true;
    @try {
        NSFileHandle *handle = nil;
        if (!EnsureDiagnosticOutputFile(&handle)) return false;
        for (uint32_t i = 0; i < gRingCount; ++i) {
            NSData *data = [NSData dataWithBytes:gRing[i].serialized length:strlen(gRing[i].serialized)];
            [handle writeData:data];
        }
        [handle synchronizeFile];
        [handle closeFile];
    } @catch (...) {
        return false;
    }
    gRingCount = 0;
    return true;
}

static void DisableLoggingForSession(void) {
    gLoggingDisabled.store(true, std::memory_order_release);
}

static bool BeginObserver(bool verboseOnly) {
    if (gInDiagnosticObserver || gLoggingDisabled.load(std::memory_order_acquire) ||
        !gDiagnosticEnabled.load(std::memory_order_acquire) ||
        (verboseOnly && !gDiagnosticVerbose.load(std::memory_order_acquire))) return false;
    gInDiagnosticObserver = true;
    return true;
}

static void EndObserver(void) {
    gInDiagnosticObserver = false;
}

static void CopyPackageDetails(id description, char *packageName, size_t packageCapacity,
                               char *pathPrefix, size_t prefixCapacity, char *descriptionClass,
                               size_t classCapacity) {
    packageName[0] = pathPrefix[0] = descriptionClass[0] = '\0';
    if (!description) return;
    CopySafe(descriptionClass, classCapacity, NSStringFromClass(object_getClass(description)));
    @try {
        if (![description respondsToSelector:@selector(packageURL)]) return;
        id packageURL = ((id(*)(id, SEL))objc_msgSend)(description, @selector(packageURL));
        if (![packageURL isKindOfClass:[NSURL class]]) return;
        NSString *path = [(NSURL *)packageURL path];
        NSString *last = [path lastPathComponent];
        CopySafe(packageName, packageCapacity, [last stringByDeletingPathExtension]);
        if ([path hasPrefix:@"/private/"]) CopySafeCString(pathPrefix, prefixCapacity, "private");
        else if ([path hasPrefix:@"/var/"]) CopySafeCString(pathPrefix, prefixCapacity, "var");
        else if ([path rangeOfString:@"/Containers/"].location != NSNotFound) CopySafeCString(pathPrefix, prefixCapacity, "app-container");
        else if ([path hasPrefix:@"/Applications/"]) CopySafeCString(pathPrefix, prefixCapacity, "Applications");
        else CopySafeCString(pathPrefix, prefixCapacity, "other");
    } @catch (...) {
        packageName[0] = pathPrefix[0] = '\0';
    }
}

static void CopyStateDetails(id state, char *destination, size_t capacity) {
    if (!state) {
        destination[0] = '\0';
    } else if ([state isKindOfClass:[NSString class]]) {
        CopySafe(destination, capacity, state);
    } else {
        CopySafe(destination, capacity, NSStringFromClass(object_getClass(state)));
    }
}

static int32_t ViewTag(id view) {
    if (!view || ![view respondsToSelector:@selector(tag)]) return 0;
    @try { return ((NSInteger(*)(id, SEL))objc_msgSend)(view, @selector(tag)); }
    @catch (...) { return 0; }
}

static void CopyAncestorClass(id view, char *destination, size_t capacity) {
    destination[0] = '\0';
    if (!view) return;
    @try {
        SEL selector = NSSelectorFromString(@"_viewControllerForAncestor");
        if (![view respondsToSelector:selector]) return;
        id controller = ((id(*)(id, SEL))objc_msgSend)(view, selector);
        if (controller) CopySafe(destination, capacity, NSStringFromClass(object_getClass(controller)));
    } @catch (...) {
        destination[0] = '\0';
    }
}

static bool DescriptionIsNewLocked(id view, id description) {
    const void *viewPointer = (__bridge const void *)view;
    const void *descriptionPointer = (__bridge const void *)description;
    if (!viewPointer) return false;
    for (uint32_t i = 0; i < gSeenDescriptionCount; ++i) {
        if (gSeenDescriptions[i].view == viewPointer) {
            bool isNew = gSeenDescriptions[i].description != descriptionPointer;
            gSeenDescriptions[i].description = descriptionPointer;
            return isNew;
        }
    }
    if (gSeenDescriptionCount < sizeof(gSeenDescriptions) / sizeof(gSeenDescriptions[0])) {
        gSeenDescriptions[gSeenDescriptionCount++] = { viewPointer, descriptionPointer };
    } else {
        gSeenDescriptions[0] = { viewPointer, descriptionPointer };
    }
    return true;
}

static bool TupleOrPairIsDuplicateLocked(CAMLDiagnosticEvent *event, bool *serializationFailed) {
    *serializationFailed = false;
    char tuple[128] = {};
    char pair[96] = {};
    snprintf(tuple, sizeof(tuple), "%s|%s|%s", event->site, event->packageName, event->state);
    snprintf(pair, sizeof(pair), "%s|%s", event->site, event->packageName);
    uint64_t now = event->monotonicMs;
    if (strcmp(tuple, gLastTuple) == 0 && now >= gLastTupleMs && now - gLastTupleMs <= kTupleDedupWindowMs) {
        if (now - gLastTupleMs <= kRepeatCollapseWindowMs && gRingCount > 0) {
            CAMLDiagnosticEvent *previous = &gRing[gLastRingIndex];
            if (previous->repeat < UINT32_MAX) ++previous->repeat;
            if (!SerializeEvent(previous)) *serializationFailed = true;
        }
        gLastTupleMs = now;
        return true;
    }
    if (strcmp(pair, gLastPair) == 0 && now >= gLastPairMs && now - gLastPairMs <= kRepeatCollapseWindowMs) {
        if (gRingCount > 0) {
            CAMLDiagnosticEvent *previous = &gRing[gLastRingIndex];
            if (previous->repeat < UINT32_MAX) ++previous->repeat;
            if (!SerializeEvent(previous)) *serializationFailed = true;
        }
        gLastPairMs = now;
        return true;
    }
    strncpy(gLastTuple, tuple, sizeof(gLastTuple) - 1);
    strncpy(gLastPair, pair, sizeof(gLastPair) - 1);
    gLastTupleMs = now;
    gLastPairMs = now;
    return false;
}

static void RecordEvent(const char *site, id view, id description, id state, bool verboseOnly, NSString *packageNameOverride) {
    if (!BeginObserver(verboseOnly)) return;
    @try {
        CAMLDiagnosticEvent event = {};
        event.monotonicMs = DiagnosticMonotonicMilliseconds();
        event.wallSeconds = (uint64_t)NSDate.date.timeIntervalSince1970;
        CopySafeCString(event.site, sizeof(event.site), site);
        CopyPackageDetails(description, event.packageName, sizeof(event.packageName), event.pathPrefix,
                           sizeof(event.pathPrefix), event.descriptionClass, sizeof(event.descriptionClass));
        if ([packageNameOverride isKindOfClass:[NSString class]])
            CopySafe(event.packageName, sizeof(event.packageName), packageNameOverride);
        CopyStateDetails(state, event.state, sizeof(event.state));
        CopyAncestorClass(view, event.ancestorClass, sizeof(event.ancestorClass));
        event.viewTag = ViewTag(view);
        os_unfair_lock_lock(&gDiagnosticLock);
        event.descriptionIsNew = DescriptionIsNewLocked(view, description);
        if (gSessionEventCount.load(std::memory_order_relaxed) >= kSessionEventCap) {
            os_unfair_lock_unlock(&gDiagnosticLock);
            EndObserver();
            return;
        }
        event.repeat = 1;
        event.installationRecord = strcmp(site, "install") == 0;
        bool serializationFailed = false;
        if (TupleOrPairIsDuplicateLocked(&event, &serializationFailed)) {
            os_unfair_lock_unlock(&gDiagnosticLock);
            if (serializationFailed) DisableLoggingForSession();
            EndObserver();
            return;
        }
        if (gRingCount >= kRingCapacity && !FlushRingLocked()) {
            os_unfair_lock_unlock(&gDiagnosticLock);
            DisableLoggingForSession();
            EndObserver();
            return;
        }
        if (!SerializeEvent(&event)) {
            os_unfair_lock_unlock(&gDiagnosticLock);
            DisableLoggingForSession();
            EndObserver();
            return;
        }
        gRing[gRingCount] = event;
        gLastRingIndex = gRingCount;
        ++gRingCount;
        gSessionEventCount.fetch_add(1, std::memory_order_relaxed);
        bool flush = gRingCount == kRingCapacity;
        bool flushSucceeded = !flush || FlushRingLocked();
        os_unfair_lock_unlock(&gDiagnosticLock);
        if (!flushSucceeded) DisableLoggingForSession();
    } @catch (...) {
        DisableLoggingForSession();
    }
    EndObserver();
}

static void ObservePackage(id view, id description, const char *site) {
    RecordEvent(site, view, description, nil, false, nil);
}

static void ObserveState(id view, id state, const char *site) {
    id description = nil;
    @try {
        SEL selector = @selector(glyphPackageDescription);
        if ([view respondsToSelector:selector]) description = ((id(*)(id, SEL))objc_msgSend)(view, selector);
    } @catch (...) {
        description = nil;
    }
    RecordEvent(site, view, description, state, false, nil);
}

static void ObserveFactory(id packageName, id bundle) {
    // Factory events deliberately omit package URLs and use only a bounded package-name value.
    RecordEvent("factory", nil, nil, nil, true, [packageName isKindOfClass:[NSString class]] ? packageName : nil);
    (void)bundle;
}

static void CAMLButtonPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "button-view");
    ((void(*)(id, SEL, id))gOriginalButtonPackage)(self, cmd, description);
}

static void CAMLRoundPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "round-button");
    ((void(*)(id, SEL, id))gOriginalRoundPackage)(self, cmd, description);
}

static void CAMLSliderPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "slider-view");
    ((void(*)(id, SEL, id))gOriginalSliderPackage)(self, cmd, description);
}

static id CAMLFactoryHook(id self, SEL cmd, id packageName, id bundle) {
    ObserveFactory(packageName, bundle);
    return ((id(*)(id, SEL, id, id))gOriginalFactory)(self, cmd, packageName, bundle);
}

static void CAMLButtonStateHook(id self, SEL cmd, id state) {
    ObserveState(self, state, "glyph-state");
    ((void(*)(id, SEL, id))gOriginalButtonState)(self, cmd, state);
}

static void CAMLSliderStateHook(id self, SEL cmd, id state) {
    ObserveState(self, state, "glyph-state");
    ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);
}

void CAMLDiagnosticFlushAtDismiss(void) {
    if (!gDiagnosticEnabled.load(std::memory_order_acquire) || gLoggingDisabled.load(std::memory_order_acquire)) return;
    os_unfair_lock_lock(&gDiagnosticLock);
    bool succeeded = FlushRingLocked();
    os_unfair_lock_unlock(&gDiagnosticLock);
    if (!succeeded) DisableLoggingForSession();
}

struct CAMLDiagnosticSite {
    NSString *className;
    SEL selector;
    const char *encoding;
    IMP replacement;
    IMP *original;
    bool classMethod;
};

static CAMLDiagnosticSite gSites[] = {
    { @"CCUIButtonModuleView", @selector(setGlyphPackageDescription:), "v24@0:8@16", (IMP)CAMLButtonPackageHook, &gOriginalButtonPackage, false },
    { @"CCUIRoundButton", @selector(setGlyphPackageDescription:), "v24@0:8@16", (IMP)CAMLRoundPackageHook, &gOriginalRoundPackage, false },
    { @"CCUIBaseSliderView", @selector(setGlyphPackageDescription:), "v24@0:8@16", (IMP)CAMLSliderPackageHook, &gOriginalSliderPackage, false },
    { @"CCUICAPackageDescription", @selector(descriptionForPackageNamed:inBundle:), "@32@0:8@16@24", (IMP)CAMLFactoryHook, &gOriginalFactory, true },
    { @"CCUIButtonModuleView", @selector(setGlyphState:), "v24@0:8@16", (IMP)CAMLButtonStateHook, &gOriginalButtonState, false },
    { @"CCUIBaseSliderView", @selector(setGlyphState:), "v24@0:8@16", (IMP)CAMLSliderStateHook, &gOriginalSliderState, false },
};

static bool InstallSite(const CAMLDiagnosticSite &site) {
    Class target = objc_getClass(site.className.UTF8String);
    if (!target) return false;
    Method method = site.classMethod ? class_getClassMethod(target, site.selector) : class_getInstanceMethod(target, site.selector);
    if (!method) return false;
    const char *runtimeEncoding = method_getTypeEncoding(method);
    if (!ABIShapeMatches(runtimeEncoding, site.encoding)) return false;
    Class hookClass = site.classMethod ? object_getClass(target) : target;
    MSHookMessageEx(hookClass, site.selector, site.replacement, site.original);
    return *site.original != NULL;
}

static void RefreshDiagnosticPreferences(void) {
    @try {
        NSUserDefaults *preferences = [[NSUserDefaults alloc] initWithSuiteName:kDiagnosticPrefsDomain];
        gDiagnosticEnabled.store([preferences boolForKey:kDiagnosticEnabledKey], std::memory_order_release);
        gDiagnosticVerbose.store([preferences boolForKey:kDiagnosticVerboseKey], std::memory_order_release);
    } @catch (...) {
        gDiagnosticEnabled.store(false, std::memory_order_release);
        gDiagnosticVerbose.store(false, std::memory_order_release);
    }
}

static void DiagnosticPreferencesChanged(CFNotificationCenterRef center, void *observer, CFStringRef name,
                                         const void *object, CFDictionaryRef userInfo) {
    (void)center; (void)observer; (void)name; (void)object; (void)userInfo;
    RefreshDiagnosticPreferences();
}

__attribute__((constructor)) static void InitializeCAMLDiagnostic(void) {
    @try {
        DiagnosticUUID();
        RefreshDiagnosticPreferences();
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL,
                                        DiagnosticPreferencesChanged, (__bridge CFStringRef)kDiagnosticPrefsChanged,
                                        NULL, CFNotificationSuspensionBehaviorDeliverImmediately);
        for (const CAMLDiagnosticSite &site : gSites) (void)InstallSite(site);
        // The hook chain is installed once; disabled/default and preference transitions are no-op observer bodies.
        if (gDiagnosticEnabled.load(std::memory_order_acquire)) RecordEvent("install", nil, nil, nil, false, nil);
    } @catch (...) {
        DisableLoggingForSession();
    }
}

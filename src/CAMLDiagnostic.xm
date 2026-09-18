// CAML phase-one observer-only diagnostic for iOS 17.
// This module never replaces a package description, glyph state, argument, or return value.
#import <UIKit/UIKit.h>
#import <CoreFoundation/CoreFoundation.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>
#import <rootless.h>
#import <mach-o/loader.h>
#import <dlfcn.h>
#import <os/lock.h>
#import <sys/stat.h>
#import <sys/types.h>
#import <mach/mach_time.h>
#import <errno.h>
#import <fcntl.h>
#import <unistd.h>
#import <limits.h>
#import "CAMLDiagnostic.h"
#include <atomic>
#include <stdio.h>
#include <string.h>

static const char kDiagnosticPrefsDomain[] = "com.misakaproject.plampyCC";
static CFStringRef const kDiagnosticPrefsChanged = CFSTR("com.misakaproject.plampyCC.settingsChanged");
static const char kDiagnosticEnabledKey[] = "kDiagnosticEnabled";
static const char kDiagnosticVerboseKey[] = "kDiagnosticVerbose";
static const char kDiagnosticBuildId[] = "plampycc-caml-observer-v1";
static const char kDiagnosticEventFile[] = "events.jsonl";
static const char kDiagnosticTempFile[] = "events.jsonl.tmp";
static constexpr size_t kDiagnosticSiteCount = 6;
static constexpr size_t kRingCapacity = 512;
static constexpr size_t kSerializedEventCapacity = 256;
static constexpr size_t kDiagnosticPathCapacity = PATH_MAX;
static constexpr size_t kDiagnosticRetentionBytes = 1024 * 1024;
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
    bool installationSucceeded;
    uint32_t repeat;
    char serialized[kSerializedEventCapacity];
};

struct CAMLSeenDescription {
    const void *view;
    const void *description;
};

struct CAMLDiagnosticSite {
    const char *className;
    const char *selectorName;
    const char *encoding;
    const char *label;
    IMP replacement;
    IMP *original;
    bool classMethod;
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
static unsigned char gRetentionBuffer[kDiagnosticRetentionBytes];

static bool SerializeEvent(CAMLDiagnosticEvent *event);

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

static const char * const kUnknownPackage = "unknown";
static const char * const kUnknownState = "unknown-state";
static const char * const kUnknownClass = "unknown-class";
static const char * const kApprovedPackages[] = {
    "AirplaneMode", "Bluetooth", "Calculator", "Camera", "Flashlight", "Focus",
    "LowPower", "MusicRecognition", "Timer", "WiFi"
};
static const char * const kApprovedStates[] = {
    "default", "disabled", "expanded", "highlighted", "collapsed", "off", "on", "selected"
};
static const char * const kApprovedClasses[] = {
    "CCUIButtonModuleView", "CCUIButtonModuleViewController", "CCUIRoundButton",
    "CCUILabeledRoundButton", "CCUILabeledRoundButtonController", "CCUIBaseSliderView",
    "CCUICAPackageDescription", "CCUICAPackageView", "CCUIToggleModule", "CCUIAppearanceModule",
    "CCUIMuteModule", "CCUIOrientationLockModule", "CCUILowPowerModuleViewController"
};

static void CopyFixedCString(char *destination, size_t capacity, const char *value) {
    if (capacity == 0) return;
    destination[0] = '\0';
    if (value) snprintf(destination, capacity, "%s", value);
}

static bool ApprovedValue(NSString *value, const char * const *allowlist, size_t count, const char **approved) {
    if (approved) *approved = nullptr;
    if (!value) return false;
    for (size_t i = 0; i < count; ++i) {
        NSString *candidate = [NSString stringWithUTF8String:allowlist[i]];
        if ([value isEqualToString:candidate]) {
            if (approved) *approved = allowlist[i];
            return true;
        }
    }
    return false;
}

static void CopyApproved(char *destination, size_t capacity, NSString *value,
                         const char * const *allowlist, size_t count, const char *fallback) {
    if (capacity == 0) return;
    const char *approved = nullptr;
    CopyFixedCString(destination, capacity,
                     ApprovedValue(value, allowlist, count, &approved) ? approved : fallback);
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

class CAMLScopedFD {
public:
    explicit CAMLScopedFD(int descriptor = -1) : descriptor_(descriptor) {}
    CAMLScopedFD(const CAMLScopedFD &) = delete;
    CAMLScopedFD &operator=(const CAMLScopedFD &) = delete;
    ~CAMLScopedFD() { Close(); }

    int get() const { return descriptor_; }
    bool Valid() const { return descriptor_ >= 0; }
    int Release() {
        int result = descriptor_;
        descriptor_ = -1;
        return result;
    }
    bool Close() {
        if (descriptor_ < 0) return true;
        int result = close(descriptor_);
        descriptor_ = -1;
        return result == 0;
    }
    bool Reset(int descriptor) {
        bool closed = Close();
        descriptor_ = descriptor;
        return closed;
    }

private:
    int descriptor_;
};

class CAMLScopedTempFile {
public:
    CAMLScopedTempFile(int directory, const char *name, int descriptor)
        : directory_(directory), name_(name), descriptor_(descriptor), committed_(false) {}
    CAMLScopedTempFile(const CAMLScopedTempFile &) = delete;
    CAMLScopedTempFile &operator=(const CAMLScopedTempFile &) = delete;
    ~CAMLScopedTempFile() {
        if (descriptor_ >= 0) close(descriptor_);
        if (!committed_ && directory_ >= 0) unlinkat(directory_, name_, 0);
    }

    bool Valid() const { return descriptor_ >= 0; }
    int get() const { return descriptor_; }
    bool Close() {
        if (descriptor_ < 0) return true;
        int result = close(descriptor_);
        descriptor_ = -1;
        return result == 0;
    }
    void Commit() { committed_ = true; }

private:
    int directory_;
    const char *name_;
    int descriptor_;
    bool committed_;
};

static NSString *DiagnosticOutputDirectory(void) {
    return ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic");
}

static bool ValidateDirectoryFD(int descriptor, bool leaf) {
    struct stat status = {};
    if (fstat(descriptor, &status) != 0 || !S_ISDIR(status.st_mode)) return false;
    if (leaf && status.st_uid != geteuid()) return false;
    if (leaf) return (status.st_mode & 0777) == 0700;
    return (status.st_mode & 0022) == 0;
}

static bool ValidateEventFD(int descriptor, size_t *size) {
    struct stat status = {};
    if (fstat(descriptor, &status) != 0 || !S_ISREG(status.st_mode)) return false;
    if (status.st_uid != geteuid() || (status.st_mode & 0777) != 0600) return false;
    if (status.st_size < 0 || (uint64_t)status.st_size > kDiagnosticRetentionBytes) return false;
    if (size) *size = (size_t)status.st_size;
    return true;
}

static bool OpenDiagnosticDirectory(int *descriptor) {
    if (!descriptor) return false;
    *descriptor = -1;
    @try {
        NSString *directory = DiagnosticOutputDirectory();
        const char *source = directory.fileSystemRepresentation;
        if (!source) return false;
        char path[kDiagnosticPathCapacity] = {};
        if (strlcpy(path, source, sizeof(path)) >= sizeof(path)) return false;

        CAMLScopedFD current(open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
        if (!current.Valid() || !ValidateDirectoryFD(current.get(), false)) return false;
        char *cursor = path;
        bool sawComponent = false;
        for (;;) {
            while (*cursor == '/') ++cursor;
            if (*cursor == '\0') break;
            char *component = cursor;
            while (*cursor != '\0' && *cursor != '/') ++cursor;
            if (*cursor == '/') {
                *cursor = '\0';
                ++cursor;
            }
            while (*cursor == '/') ++cursor;
            bool leaf = *cursor == '\0';
            if (component[0] == '\0' || strcmp(component, ".") == 0 || strcmp(component, "..") == 0)
                return false;
            CAMLScopedFD next(openat(current.get(), component,
                                     O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
            if (!next.Valid() && errno == ENOENT) {
                if (mkdirat(current.get(), component, 0700) != 0 && errno != EEXIST) return false;
                next.Reset(openat(current.get(), component,
                                  O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
            }
            if (!next.Valid() || !ValidateDirectoryFD(next.get(), leaf)) return false;
            if (!current.Reset(next.Release())) return false;
            sawComponent = true;
            if (leaf) break;
        }
        if (!sawComponent) return false;
        *descriptor = current.Release();
        return true;
    } @catch (...) {
        return false;
    }
}

static bool ReadExistingEvents(int directory, size_t *size) {
    if (!size) return false;
    *size = 0;
    CAMLScopedFD descriptor(openat(directory, kDiagnosticEventFile, O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
    if (!descriptor.Valid()) return errno == ENOENT;
    size_t length = 0;
    if (!ValidateEventFD(descriptor.get(), &length)) return false;
    size_t offset = 0;
    while (offset < length) {
        ssize_t count = pread(descriptor.get(), gRetentionBuffer + offset, length - offset, (off_t)offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return false;
        offset += (size_t)count;
    }
    if (!descriptor.Close()) return false;
    *size = length;
    return true;
}

static size_t CompleteLinePrefix(size_t size) {
    while (size > 0 && gRetentionBuffer[size - 1] != '\n') --size;
    return size;
}

static bool WriteAll(int descriptor, const void *bytes, size_t length) {
    const unsigned char *cursor = (const unsigned char *)bytes;
    while (length > 0) {
        ssize_t count = write(descriptor, cursor, length);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return false;
        cursor += count;
        length -= (size_t)count;
    }
    return true;
}

static int OpenTemporaryEvents(int directory) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        CAMLScopedFD descriptor(openat(directory, kDiagnosticTempFile,
                                       O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600));
        if (descriptor.Valid()) {
            size_t size = 0;
            if (ValidateEventFD(descriptor.get(), &size) && size == 0) return descriptor.Release();
            unlinkat(directory, kDiagnosticTempFile, 0);
            return -1;
        }
        if (errno != EEXIST || attempt != 0) return -1;
        CAMLScopedFD stale(openat(directory, kDiagnosticTempFile, O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
        if (!stale.Valid()) return -1;
        if (!ValidateEventFD(stale.get(), nullptr) || !stale.Close() ||
            unlinkat(directory, kDiagnosticTempFile, 0) != 0) return -1;
    }
    return -1;
}

static size_t PendingEventBytes(void) {
    size_t total = 0;
    for (uint32_t i = 0; i < gRingCount; ++i) {
        size_t length = strlen(gRing[i].serialized);
        if (length > kDiagnosticRetentionBytes - total) return 0;
        total += length;
    }
    return total;
}

// Atomic replace preserves the old complete file until the new complete file is durable.
static bool FlushRingLocked(void) {
    if (gRingCount == 0) return true;
    int directory = -1;
    bool succeeded = false;
    @try {
        if (!OpenDiagnosticDirectory(&directory)) return false;
        CAMLScopedFD directoryGuard(directory);
        size_t existingSize = 0;
        if (!ReadExistingEvents(directory, &existingSize)) return false;
        existingSize = CompleteLinePrefix(existingSize);
        size_t pendingSize = PendingEventBytes();
        if (pendingSize == 0 || pendingSize > kDiagnosticRetentionBytes) return false;
        size_t keepExisting = kDiagnosticRetentionBytes - pendingSize;
        size_t firstExisting = existingSize > keepExisting ? existingSize - keepExisting : 0;
        if (firstExisting > 0) {
            while (firstExisting < existingSize && gRetentionBuffer[firstExisting - 1] != '\n') ++firstExisting;
        }
        int temporaryDescriptor = OpenTemporaryEvents(directory);
        if (temporaryDescriptor < 0) return false;
        CAMLScopedTempFile temporaryGuard(directory, kDiagnosticTempFile, temporaryDescriptor);
        if (!temporaryGuard.Valid()) return false;
        if (!WriteAll(temporaryGuard.get(), gRetentionBuffer + firstExisting, existingSize - firstExisting)) return false;
        for (uint32_t i = 0; i < gRingCount; ++i) {
            size_t length = strlen(gRing[i].serialized);
            if (!WriteAll(temporaryGuard.get(), gRing[i].serialized, length)) return false;
        }
        if (fsync(temporaryGuard.get()) != 0 || !temporaryGuard.Close()) return false;
        if (renameat(directory, kDiagnosticTempFile, directory, kDiagnosticEventFile) != 0) return false;
        temporaryGuard.Commit();
        if (fsync(directory) != 0) return false;
        if (!directoryGuard.Close()) return false;
        gRingCount = 0;
        succeeded = true;
    } @catch (...) {
        succeeded = false;
    }
    return succeeded;
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
    CopyApproved(descriptionClass, classCapacity, NSStringFromClass(object_getClass(description)),
                 kApprovedClasses, sizeof(kApprovedClasses) / sizeof(kApprovedClasses[0]), kUnknownClass);
    if (![description respondsToSelector:@selector(packageURL)]) return;
    id packageURL = ((id(*)(id, SEL))objc_msgSend)(description, @selector(packageURL));
    if (![packageURL isKindOfClass:[NSURL class]]) return;
    NSString *path = [(NSURL *)packageURL path];
    NSString *last = [path lastPathComponent];
    CopyApproved(packageName, packageCapacity, [last stringByDeletingPathExtension],
                 kApprovedPackages, sizeof(kApprovedPackages) / sizeof(kApprovedPackages[0]), kUnknownPackage);
    if ([path hasPrefix:@"/private/"]) CopyFixedCString(pathPrefix, prefixCapacity, "private");
    else if ([path hasPrefix:@"/var/"]) CopyFixedCString(pathPrefix, prefixCapacity, "var");
    else if ([path rangeOfString:@"/Containers/"].location != NSNotFound) CopyFixedCString(pathPrefix, prefixCapacity, "app-container");
    else if ([path hasPrefix:@"/Applications/"]) CopyFixedCString(pathPrefix, prefixCapacity, "Applications");
    else CopyFixedCString(pathPrefix, prefixCapacity, "other");
}

static void CopyStateDetails(id state, char *destination, size_t capacity) {
    if (!state) {
        destination[0] = '\0';
    } else if ([state isKindOfClass:[NSString class]]) {
        CopyApproved(destination, capacity, state, kApprovedStates,
                    sizeof(kApprovedStates) / sizeof(kApprovedStates[0]), kUnknownState);
    } else {
        CopyApproved(destination, capacity, NSStringFromClass(object_getClass(state)),
                     kApprovedClasses, sizeof(kApprovedClasses) / sizeof(kApprovedClasses[0]), kUnknownState);
    }
}

static int32_t ViewTag(id view) {
    if (!view || ![view respondsToSelector:@selector(tag)]) return 0;
    return ((NSInteger(*)(id, SEL))objc_msgSend)(view, @selector(tag));
}

static void CopyAncestorClass(id view, char *destination, size_t capacity) {
    destination[0] = '\0';
    if (!view) return;
    SEL selector = NSSelectorFromString(@"_viewControllerForAncestor");
    if (![view respondsToSelector:selector]) return;
    id controller = ((id(*)(id, SEL))objc_msgSend)(view, selector);
    if (controller) CopyApproved(destination, capacity, NSStringFromClass(object_getClass(controller)),
                                  kApprovedClasses, sizeof(kApprovedClasses) / sizeof(kApprovedClasses[0]), kUnknownClass);
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

static bool SerializeEvent(CAMLDiagnosticEvent *event) {
    const char *buildId = event->installationRecord ? kDiagnosticBuildId : "";
    const char *uuid = event->installationRecord ? gDiagnosticUUID : "";
    uint64_t serializedMonotonic = event->monotonicMs % 10000000000000ULL;
    uint32_t serializedWall = event->wallSeconds > UINT32_MAX ? UINT32_MAX : (uint32_t)event->wallSeconds;
    int written = snprintf(event->serialized, sizeof(event->serialized),
                           "{\"v\":1,\"t\":%llu,\"w\":%u,\"s\":\"%.12s\",\"p\":\"%.20s\",\"x\":\"%.12s\",\"n\":%d,\"g\":\"%.12s\",\"d\":\"%.20s\",\"i\":%d,\"a\":\"%.20s\",\"r\":%u,\"q\":%d,\"b\":\"%.25s\",\"u\":\"%.36s\"}\n",
                           (unsigned long long)serializedMonotonic, serializedWall,
                           event->site, event->packageName, event->pathPrefix,
                           event->descriptionIsNew ? 1 : 0, event->state,
                           event->descriptionClass, event->viewTag, event->ancestorClass,
                           event->repeat, event->installationSucceeded ? 1 : 0, buildId, uuid);
    return written > 0 && (size_t)written < sizeof(event->serialized);
}

static void RecordEventBody(const char *site, id view, id description, id state,
                            NSString *packageNameOverride, bool installationRecord,
                            bool installationSucceeded) {
    CAMLDiagnosticEvent event = {};
    event.monotonicMs = DiagnosticMonotonicMilliseconds();
    event.wallSeconds = (uint64_t)NSDate.date.timeIntervalSince1970;
    CopyFixedCString(event.site, sizeof(event.site), site);
    CopyPackageDetails(description, event.packageName, sizeof(event.packageName), event.pathPrefix,
                       sizeof(event.pathPrefix), event.descriptionClass, sizeof(event.descriptionClass));
    if ([packageNameOverride isKindOfClass:[NSString class]])
        CopyApproved(event.packageName, sizeof(event.packageName), packageNameOverride,
                     kApprovedPackages, sizeof(kApprovedPackages) / sizeof(kApprovedPackages[0]), kUnknownPackage);
    CopyStateDetails(state, event.state, sizeof(event.state));
    CopyAncestorClass(view, event.ancestorClass, sizeof(event.ancestorClass));
    event.viewTag = ViewTag(view);
    event.installationRecord = installationRecord;
    event.installationSucceeded = installationSucceeded;
    os_unfair_lock_lock(&gDiagnosticLock);
    event.descriptionIsNew = DescriptionIsNewLocked(view, description);
    if (gSessionEventCount.load(std::memory_order_relaxed) >= kSessionEventCap) {
        os_unfair_lock_unlock(&gDiagnosticLock);
        return;
    }
    event.repeat = 1;
    bool serializationFailed = false;
    if (TupleOrPairIsDuplicateLocked(&event, &serializationFailed)) {
        os_unfair_lock_unlock(&gDiagnosticLock);
        if (serializationFailed) DisableLoggingForSession();
        return;
    }
    if (gRingCount >= kRingCapacity && !FlushRingLocked()) {
        os_unfair_lock_unlock(&gDiagnosticLock);
        DisableLoggingForSession();
        return;
    }
    if (!SerializeEvent(&event)) {
        os_unfair_lock_unlock(&gDiagnosticLock);
        DisableLoggingForSession();
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
}

typedef void (*CAMLDiagnosticBody)(void *context);

static void RunObserver(bool verboseOnly, CAMLDiagnosticBody body, void *context) {
    bool entered = false;
    @try {
        if (!BeginObserver(verboseOnly)) return;
        entered = true;
        body(context);
    } @catch (...) {
        DisableLoggingForSession();
    } @finally {
        if (entered) EndObserver();
    }
}

// Hook arguments are borrowed only for this synchronous diagnostic call. Unsafe-unretained
// fields keep ARC ownership work inside RunObserver's guarded body; the original still owns
// its normal invocation arguments and is called after this context is gone.
struct CAMLPackageContext { __unsafe_unretained id view; __unsafe_unretained id description; const char *site; };
static void ObservePackageBody(void *rawContext) {
    CAMLPackageContext *context = (CAMLPackageContext *)rawContext;
    RecordEventBody(context->site, context->view, context->description, nil, nil, false, false);
}
__attribute__((noinline, used)) static void ObservePackage(id view, id description, const char *site) {
    CAMLPackageContext context = { view, description, site };
    RunObserver(false, ObservePackageBody, &context);
}

struct CAMLStateContext { __unsafe_unretained id view; __unsafe_unretained id state; const char *site; };
static void ObserveStateBody(void *rawContext) {
    CAMLStateContext *context = (CAMLStateContext *)rawContext;
    id description = nil;
    SEL selector = @selector(glyphPackageDescription);
    if ([context->view respondsToSelector:selector])
        description = ((id(*)(id, SEL))objc_msgSend)(context->view, selector);
    RecordEventBody(context->site, context->view, description, context->state, nil, false, false);
}
__attribute__((noinline, used)) static void ObserveState(id view, id state, const char *site) {
    CAMLStateContext context = { view, state, site };
    RunObserver(false, ObserveStateBody, &context);
}

struct CAMLFactoryContext { __unsafe_unretained id packageName; };
static void ObserveFactoryBody(void *rawContext) {
    CAMLFactoryContext *context = (CAMLFactoryContext *)rawContext;
    NSString *packageName = [context->packageName isKindOfClass:[NSString class]] ? context->packageName : nil;
    RecordEventBody("factory", nil, nil, nil, packageName, false, false);
}
__attribute__((noinline, used)) static void ObserveFactory(id packageName) {
    CAMLFactoryContext context = { packageName };
    RunObserver(true, ObserveFactoryBody, &context);
}

static void CAMLButtonPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "button-view");
    if (gOriginalButtonPackage) ((void(*)(id, SEL, id))gOriginalButtonPackage)(self, cmd, description);
}

static void CAMLRoundPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "round-button");
    if (gOriginalRoundPackage) ((void(*)(id, SEL, id))gOriginalRoundPackage)(self, cmd, description);
}

static void CAMLSliderPackageHook(id self, SEL cmd, id description) {
    ObservePackage(self, description, "slider-view");
    if (gOriginalSliderPackage) ((void(*)(id, SEL, id))gOriginalSliderPackage)(self, cmd, description);
}

static id CAMLFactoryHook(id self, SEL cmd, id packageName, id bundle) {
    ObserveFactory(packageName);
    return gOriginalFactory ? ((id(*)(id, SEL, id, id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;
}

static void CAMLButtonStateHook(id self, SEL cmd, id state) {
    ObserveState(self, state, "glyph-state");
    if (gOriginalButtonState) ((void(*)(id, SEL, id))gOriginalButtonState)(self, cmd, state);
}

static void CAMLSliderStateHook(id self, SEL cmd, id state) {
    ObserveState(self, state, "glyph-state");
    if (gOriginalSliderState) ((void(*)(id, SEL, id))gOriginalSliderState)(self, cmd, state);
}

struct CAMLInstallContext { const char *site; bool succeeded; };
static void RecordInstallStatusBody(void *rawContext) {
    CAMLInstallContext *context = (CAMLInstallContext *)rawContext;
    RecordEventBody(context->site, nil, nil, nil, nil, true, context->succeeded);
}
static void RecordInstallStatus(const CAMLDiagnosticSite *site, bool succeeded) {
    CAMLInstallContext context = { site->label, succeeded };
    RunObserver(false, RecordInstallStatusBody, &context);
}

static void FlushObserverBody(void *context) {
    (void)context;
    os_unfair_lock_lock(&gDiagnosticLock);
    bool succeeded = FlushRingLocked();
    os_unfair_lock_unlock(&gDiagnosticLock);
    if (!succeeded) DisableLoggingForSession();
}

extern "C" void CAMLDiagnosticFlushAtDismiss(void) {
    RunObserver(false, FlushObserverBody, nil);
}

static bool InstallSite(const CAMLDiagnosticSite *site) {
    if (!site || !site->className || !site->selectorName || !site->encoding || !site->replacement || !site->original) return false;
    Class target = objc_getClass(site->className);
    if (!target) return false;
    SEL selector = sel_registerName(site->selectorName);
    Method method = site->classMethod ? class_getClassMethod(target, selector) : class_getInstanceMethod(target, selector);
    if (!method) return false;
    const char *runtimeEncoding = method_getTypeEncoding(method);
    if (!ABIShapeMatches(runtimeEncoding, site->encoding)) return false;
    Class hookClass = site->classMethod ? object_getClass(target) : target;
    MSHookMessageEx(hookClass, selector, site->replacement, site->original);
    return *site->original != NULL;
}

// POD descriptors are populated synchronously by the caller before the installer sees them.
__attribute__((noinline, used)) static size_t BuildCAMLDiagnosticSites(CAMLDiagnosticSite *sites, size_t capacity) {
    if (!sites || capacity < kDiagnosticSiteCount) return 0;
    sites[0] = { "CCUIButtonModuleView", "setGlyphPackageDescription:", "v24@0:8@16", "button-package", (IMP)CAMLButtonPackageHook, &gOriginalButtonPackage, false };
    sites[1] = { "CCUIRoundButton", "setGlyphPackageDescription:", "v24@0:8@16", "round-package", (IMP)CAMLRoundPackageHook, &gOriginalRoundPackage, false };
    sites[2] = { "CCUIBaseSliderView", "setGlyphPackageDescription:", "v24@0:8@16", "slider-package", (IMP)CAMLSliderPackageHook, &gOriginalSliderPackage, false };
    sites[3] = { "CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:", "@32@0:8@16@24", "factory", (IMP)CAMLFactoryHook, &gOriginalFactory, true };
    sites[4] = { "CCUIButtonModuleView", "setGlyphState:", "v24@0:8@16", "button-state", (IMP)CAMLButtonStateHook, &gOriginalButtonState, false };
    sites[5] = { "CCUIBaseSliderView", "setGlyphState:", "v24@0:8@16", "slider-state", (IMP)CAMLSliderStateHook, &gOriginalSliderState, false };
    return kDiagnosticSiteCount;
}

__attribute__((noinline, used)) static void InstallCAMLDiagnosticSites(CAMLDiagnosticSite *sites, size_t count) {
    for (size_t index = 0; index < count; ++index) {
        bool succeeded = InstallSite(&sites[index]);
        RecordInstallStatus(&sites[index], succeeded);
    }
}

static void RefreshDiagnosticPreferences(void) {
    @try {
        NSString *domain = [NSString stringWithUTF8String:kDiagnosticPrefsDomain];
        NSUserDefaults *preferences = [[NSUserDefaults alloc] initWithSuiteName:domain];
        gDiagnosticEnabled.store([preferences boolForKey:[NSString stringWithUTF8String:kDiagnosticEnabledKey]], std::memory_order_release);
        gDiagnosticVerbose.store([preferences boolForKey:[NSString stringWithUTF8String:kDiagnosticVerboseKey]], std::memory_order_release);
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
                                        DiagnosticPreferencesChanged, kDiagnosticPrefsChanged,
                                        NULL, CFNotificationSuspensionBehaviorDeliverImmediately);
        CAMLDiagnosticSite sites[kDiagnosticSiteCount] = {};
        size_t siteCount = BuildCAMLDiagnosticSites(sites, kDiagnosticSiteCount);
        if (siteCount == kDiagnosticSiteCount) InstallCAMLDiagnosticSites(sites, siteCount);
    } @catch (...) {
        DisableLoggingForSession();
    }
}

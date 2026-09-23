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
#include "CAMLDiagnosticCore.hpp"
#include "CAMLDiagnosticIO.hpp"
#include "CAMLReplacementCore.hpp"
#import "PlampyCCState.h"

static const char kDiagnosticPrefsDomain[] = "com.misakaproject.plampyCC";
static CFStringRef const kDiagnosticPrefsChanged = CFSTR("com.misakaproject.plampyCC.settingsChanged");
static const char kDiagnosticVerboseKey[] = "kDiagnosticVerbose";
#if defined(PLAMPYCC_DIAGNOSTIC_BUILD)
// Collector build: the bounded recorder is compiled in and records by default.
// This compile-time constant is what supersedes cfprefsd: recording cannot be
// lost to a preference read failure, a preference reset, or a missing
// diagnostic key (the functional kDiagnosticEnabled preference is superseded).
static const bool kDiagnosticCompileEnabled = true;
// Distinct build identifier so collector evidence is unambiguous about which
// binary produced it (design contract section 5, requirement 3).
static const char kDiagnosticBuildId[] = "plampycc-caml-observer-v2-diag";
#else
// Release build: the hook-and-record surface stays compiled and verified, but
// the recorder is disabled by the compile-time constant — no preference state
// can make a release binary record, and collector evidence can never come
// from an ambiguous binary.
static const bool kDiagnosticCompileEnabled = false;
static const char kDiagnosticBuildId[] = "plampycc-caml-observer-v2";
#endif
static const char kDiagnosticEventFile[] = "events.jsonl";
static const char kDiagnosticTempFile[] = "events.jsonl.tmp";

extern caml_diag::SyscallAdapter gDarwinSyscalls;
static constexpr size_t kDiagnosticSiteCount = 7;
static constexpr size_t kRingCapacity = caml_diag::RingPolicy::kCapacity;
static constexpr size_t kSerializedEventCapacity = caml_diag::RingPolicy::kSerializedEventCapacity;
static constexpr size_t kDiagnosticPathCapacity = PATH_MAX;
static constexpr size_t kDiagnosticRetentionBytes = 1024 * 1024;

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
    char consumerClass[40];
    char constructionPath[16];
    char sourceURLForm[16];
    char proposedURLForm[16];
    char loadOutcome[16];
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
static caml_diag::RingPolicy gRingPolicy;
static caml_diag::DedupPolicy gDedupPolicy;
static uint32_t gLastRingIndex = 0;
static unsigned char gRetentionBuffer[kDiagnosticRetentionBytes];

static bool SerializeEvent(CAMLDiagnosticEvent *event);

extern "C" IMP gOriginalButtonPackage;
extern "C" IMP gOriginalRoundPackage;
extern "C" IMP gOriginalSliderPackage;
extern "C" IMP gOriginalFactory;
extern "C" IMP gOriginalButtonState;
extern "C" IMP gOriginalSliderState;
extern "C" IMP gOriginalLowPowerDescription;
extern "C" void CAMLButtonPackageHook(id, SEL, id);
extern "C" void CAMLRoundPackageHook(id, SEL, id);
extern "C" void CAMLSliderPackageHook(id, SEL, id);
extern "C" id CAMLFactoryHook(id, SEL, id, id);
extern "C" void CAMLButtonStateHook(id, SEL, id);
extern "C" void CAMLSliderStateHook(id, SEL, id);
extern "C" id CAMLLowPowerDescriptionHook(id, SEL);

static uint64_t DiagnosticMonotonicMilliseconds(void) {
    static mach_timebase_info_data_t timebase = {};
    if (timebase.denom == 0) mach_timebase_info(&timebase);
    uint64_t nanos = mach_absolute_time() * timebase.numer / timebase.denom;
    return nanos / 1000000ULL;
}

static void CopyFixedCString(char *destination, size_t capacity, const char *value) {
    if (capacity == 0) return;
    destination[0] = '\0';
    if (value) snprintf(destination, capacity, "%s", value);
}

static void CopyApproved(char *destination, size_t capacity, NSString *value,
                         caml_diag::ValueKind kind) {
    if (capacity == 0) return;
    const char *utf8 = value ? [value UTF8String] : nullptr;
    const char *approved = caml_diag::ApprovedValue(utf8 ? std::string_view(utf8) : std::string_view(), kind);
    CopyFixedCString(destination, capacity, approved);
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
        int result = gDarwinSyscalls.close(gDarwinSyscalls.context, descriptor_);
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
        if (descriptor_ >= 0) gDarwinSyscalls.close(gDarwinSyscalls.context, descriptor_);
        if (!committed_ && directory_ >= 0)
            gDarwinSyscalls.unlinkAt(gDarwinSyscalls.context, directory_, name_);
    }

    bool Valid() const { return descriptor_ >= 0; }
    int get() const { return descriptor_; }
    bool Close() {
        if (descriptor_ < 0) return true;
        int result = gDarwinSyscalls.close(gDarwinSyscalls.context, descriptor_);
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
    NSString *primary = ROOT_PATH_NS(@"/Library/Application Support/PlampyCC/CAML-Diagnostic");
    NSString *legacy = ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic");
    BOOL primaryExists = access(primary.fileSystemRepresentation, F_OK) == 0;
    BOOL legacyExists = access(legacy.fileSystemRepresentation, F_OK) == 0;
    return primaryExists || !legacyExists ? primary : legacy;
}

static bool ValidateDirectoryFD(int descriptor, bool leaf) {
    struct stat status = {};
    if (gDarwinSyscalls.stat(gDarwinSyscalls.context, descriptor, &status) != 0 ||
        !S_ISDIR(status.st_mode)) return false;
    if (leaf && status.st_uid != geteuid()) return false;
    if (leaf) return (status.st_mode & 0777) == 0700;
    return (status.st_mode & 0022) == 0;
}

static bool ValidateEventFD(int descriptor, size_t *size) {
    struct stat status = {};
    if (gDarwinSyscalls.stat(gDarwinSyscalls.context, descriptor, &status) != 0 ||
        !S_ISREG(status.st_mode)) return false;
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
        caml_diag::PathComponents parsedPath;
        if (!caml_diag::ParsePathComponents(path, &parsedPath)) return false;
        (void)parsedPath;

        CAMLScopedFD current(gDarwinSyscalls.openAt(gDarwinSyscalls.context, AT_FDCWD, "/",
                                                      O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, 0));
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
            CAMLScopedFD next(gDarwinSyscalls.openAt(
                gDarwinSyscalls.context, current.get(), component,
                O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, 0));
            if (!next.Valid() && errno == ENOENT) {
                if (gDarwinSyscalls.makeDirectoryAt(gDarwinSyscalls.context, current.get(), component, 0700) != 0 &&
                    errno != EEXIST) return false;
                next.Reset(gDarwinSyscalls.openAt(
                    gDarwinSyscalls.context, current.get(), component,
                    O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, 0));
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
    CAMLScopedFD descriptor(gDarwinSyscalls.openAt(
        gDarwinSyscalls.context, directory, kDiagnosticEventFile,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW, 0));
    if (!descriptor.Valid()) return errno == ENOENT;
    size_t length = 0;
    if (!ValidateEventFD(descriptor.get(), &length)) return false;
    if (!caml_diag::ReadAtExact(gDarwinSyscalls, descriptor.get(), gRetentionBuffer,
                                length, 0)) return false;
    if (!descriptor.Close()) return false;
    *size = length;
    return true;
}

static size_t CompleteLinePrefix(size_t size) {
    return caml_diag::CompleteLinePrefix((const char *)gRetentionBuffer, size);
}

static int DarwinOpenAt(void *, int directory, const char *name, int flags, mode_t mode) {
    return openat(directory, name, flags, mode);
}
static int DarwinMakeDirectoryAt(void *, int directory, const char *name, mode_t mode) {
    return mkdirat(directory, name, mode);
}
static int DarwinStat(void *, int descriptor, struct stat *status) {
    return fstat(descriptor, status);
}
static ssize_t DarwinReadAt(void *, int descriptor, void *bytes, size_t length, off_t offset) {
    for (;;) {
        ssize_t result = pread(descriptor, bytes, length, offset);
        if (result < 0 && errno == EINTR) continue;
        return result;
    }
}
static ssize_t DarwinWrite(void *, int descriptor, const void *bytes, size_t length) {
    for (;;) {
        ssize_t result = write(descriptor, bytes, length);
        if (result < 0 && errno == EINTR) continue;
        return result;
    }
}
static int DarwinSync(void *, int descriptor) { return fsync(descriptor); }
static int DarwinRenameAt(void *, int fromDirectory, const char *from, int toDirectory, const char *to) {
    return renameat(fromDirectory, from, toDirectory, to);
}
static int DarwinUnlinkAt(void *, int directory, const char *name) { return unlinkat(directory, name, 0); }
static int DarwinClose(void *, int descriptor) { return close(descriptor); }
caml_diag::SyscallAdapter gDarwinSyscalls = {
    nullptr,
    DarwinOpenAt, DarwinMakeDirectoryAt, DarwinStat,
    DarwinReadAt, DarwinWrite, DarwinSync,
    DarwinRenameAt, DarwinUnlinkAt, DarwinClose
};

static bool WriteAll(int descriptor, const void *bytes, size_t length) {
    return caml_diag::WriteAll(gDarwinSyscalls, descriptor, bytes, length);
}

static int OpenTemporaryEvents(int directory) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        CAMLScopedFD descriptor(gDarwinSyscalls.openAt(gDarwinSyscalls.context, directory, kDiagnosticTempFile,
                                                   O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600));
        if (descriptor.Valid()) {
            size_t size = 0;
            if (ValidateEventFD(descriptor.get(), &size) && size == 0) return descriptor.Release();
            gDarwinSyscalls.unlinkAt(gDarwinSyscalls.context, directory, kDiagnosticTempFile);
            return -1;
        }
        if (errno != EEXIST || attempt != 0) return -1;
        CAMLScopedFD stale(gDarwinSyscalls.openAt(gDarwinSyscalls.context, directory, kDiagnosticTempFile,
                                             O_RDONLY | O_CLOEXEC | O_NOFOLLOW, 0));
        if (!stale.Valid()) return -1;
        if (!ValidateEventFD(stale.get(), nullptr) || !stale.Close() ||
            gDarwinSyscalls.unlinkAt(gDarwinSyscalls.context, directory, kDiagnosticTempFile) != 0) return -1;
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
        caml_diag::AtomicOutputState ioState;
        if (!ioState.Apply(caml_diag::AtomicOperation::Open)) return false;
        if (!OpenDiagnosticDirectory(&directory)) return false;
        CAMLScopedFD directoryGuard(directory);
        size_t existingSize = 0;
        if (!ioState.Apply(caml_diag::AtomicOperation::Validate) ||
            !ReadExistingEvents(directory, &existingSize)) return false;
        if (!ioState.Apply(caml_diag::AtomicOperation::Read)) return false;
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
        if (!temporaryGuard.Valid() || !ioState.Apply(caml_diag::AtomicOperation::TempAcquire)) return false;
        if (!WriteAll(temporaryGuard.get(), gRetentionBuffer + firstExisting, existingSize - firstExisting)) return false;
        for (uint32_t i = 0; i < gRingCount; ++i) {
            size_t length = strlen(gRing[i].serialized);
            if (!WriteAll(temporaryGuard.get(), gRing[i].serialized, length)) return false;
        }
        if (!ioState.Apply(caml_diag::AtomicOperation::Write) ||
            gDarwinSyscalls.sync(gDarwinSyscalls.context, temporaryGuard.get()) != 0 ||
            !ioState.Apply(caml_diag::AtomicOperation::FileSync) || !temporaryGuard.Close() ||
            !ioState.Apply(caml_diag::AtomicOperation::Close)) return false;
        if (gDarwinSyscalls.renameAt(gDarwinSyscalls.context, directory, kDiagnosticTempFile,
                                     directory, kDiagnosticEventFile) != 0 ||
            !ioState.Apply(caml_diag::AtomicOperation::Rename)) return false;
        temporaryGuard.Commit();
        if (gDarwinSyscalls.sync(gDarwinSyscalls.context, directory) != 0 ||
            !ioState.Apply(caml_diag::AtomicOperation::DirectorySync)) return false;
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

extern "C" bool CAMLDiagnosticPrimitiveAdmission(bool verboseOnly) {
    // This is the only pre-observer hook decision. It reads POD state only:
    // no message send, retain, allocation, logging, or filesystem operation.
    return caml_diag::AdmitObserverBody({
        gInDiagnosticObserver,
        gLoggingDisabled.load(std::memory_order_acquire),
        kDiagnosticCompileEnabled,
        gDiagnosticVerbose.load(std::memory_order_acquire),
        verboseOnly,
    });
}

static bool BeginObserver(bool verboseOnly) {
    if (!CAMLDiagnosticPrimitiveAdmission(verboseOnly)) return false;
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
                 caml_diag::ValueKind::Class);
    if (![description respondsToSelector:@selector(packageURL)]) return;
    id packageURL = ((id(*)(id, SEL))objc_msgSend)(description, @selector(packageURL));
    if (![packageURL isKindOfClass:[NSURL class]]) return;
    NSString *path = [(NSURL *)packageURL path];
    NSString *last = [path lastPathComponent];
    CopyApproved(packageName, packageCapacity, [last stringByDeletingPathExtension],
                 caml_diag::ValueKind::Package);
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
        CopyApproved(destination, capacity, state, caml_diag::ValueKind::State);
    } else {
        CopyApproved(destination, capacity, NSStringFromClass(object_getClass(state)),
                     caml_diag::ValueKind::Class);
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
                                   caml_diag::ValueKind::Class);
}

static NSString *DiagnosticPackageStem(id description, NSURL **outURL) {
    if (outURL) *outURL = nil;
    if (!description || ![description respondsToSelector:@selector(packageURL)]) return nil;
    id value = ((id(*)(id, SEL))objc_msgSend)(description, @selector(packageURL));
    if (![value isKindOfClass:NSURL.class]) return nil;
    if (outURL) *outURL = value;
    return [[(NSURL *)value URLByDeletingPathExtension] lastPathComponent];
}

static bool DiagnosticReplacementResourceExists(NSString *name, const char *bundleDirectory) {
    if (!name.length || !bundleDirectory) return false;
    NSString *theme = PlampyCCThemeType() == 1 ? @"Pulsar" : @"Plampy";
    NSArray<NSString *> *roots = @[
        ROOT_PATH_NS(@"/Library/Application Support/PlampyCC"),
        ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC")
    ];
    NSString *bundleLeaf = [NSString stringWithUTF8String:bundleDirectory];
    for (NSString *root in roots) {
        NSString *bundlePath = [[[[root stringByAppendingPathComponent:theme]
                                  stringByAppendingPathComponent:@"Assets"]
                                  stringByAppendingPathComponent:bundleLeaf] copy];
        NSBundle *bundle = [NSBundle bundleWithPath:bundlePath];
        if ([bundle URLForResource:name withExtension:@"ca"]) return true;
    }
    return false;
}

static void CopyRouteDetails(const char *site, id view, id description,
                             CAMLDiagnosticEvent *event) {
    const char *construction = caml_diag::ConstructionPathForSite(site);
    CopyFixedCString(event->constructionPath, sizeof(event->constructionPath), construction);
    if (view) CopyApproved(event->consumerClass, sizeof(event->consumerClass),
                           NSStringFromClass(object_getClass(view)), caml_diag::ValueKind::Class);

    NSURL *sourceURL = nil;
    NSString *name = DiagnosticPackageStem(description, &sourceURL);
    const char *sourceForm = caml_diag::SourceURLForm(
        description && [description respondsToSelector:@selector(packageURL)],
        sourceURL != nil, sourceURL.isFileURL);
    CopyFixedCString(event->sourceURLForm, sizeof(event->sourceURLForm), sourceForm);

    bool loadSite = caml_diag::IsLoadClassificationPath(construction);
    const char *bundleDirectory = nullptr;
    if (loadSite && name.length && PlampyCCFunctionalEnabled()) {
        caml_replacement::Site mappingSite = strcmp(construction, "slider") == 0
                                                 ? caml_replacement::Site::Slider
                                                 : caml_replacement::Site::Setter;
        bundleDirectory = caml_replacement::BundleDirectoryForPackage(
            name.UTF8String, mappingSite, PlampyCCThemeType());
    }
    bool proposed = bundleDirectory != nullptr;
    bool resolved = proposed && DiagnosticReplacementResourceExists(name, bundleDirectory);
    CopyFixedCString(event->proposedURLForm, sizeof(event->proposedURLForm),
                     caml_diag::ProposedURLForm(proposed));
    CopyFixedCString(event->loadOutcome, sizeof(event->loadOutcome),
                     caml_diag::LoadOutcomeForEvidence(proposed, resolved));
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

static bool SerializeEvent(CAMLDiagnosticEvent *event);

static bool TupleOrPairIsDuplicateLocked(CAMLDiagnosticEvent *event, bool *serializationFailed) {
    *serializationFailed = false;
    caml_diag::DuplicateDecision decision = gDedupPolicy.Decide(
        { event->site, event->packageName, event->state }, event->monotonicMs,
        gRingCount != 0, nullptr);
    if (decision == caml_diag::DuplicateDecision::Accept) return false;
    if (gRingCount == 0) return true;
    CAMLDiagnosticEvent *previous = &gRing[gLastRingIndex];
    if (previous->repeat < UINT32_MAX) ++previous->repeat;
    if (!SerializeEvent(previous)) *serializationFailed = true;
    return true;
}

static bool SerializeEvent(CAMLDiagnosticEvent *event) {
    const char *buildId = event->installationRecord ? kDiagnosticBuildId : "";
    const char *uuid = event->installationRecord ? gDiagnosticUUID : "";
    uint64_t serializedMonotonic = event->monotonicMs % 10000000000000ULL;
    uint32_t serializedWall = event->wallSeconds > UINT32_MAX ? UINT32_MAX : (uint32_t)event->wallSeconds;
    int written = snprintf(event->serialized, sizeof(event->serialized),
                           "{\"v\":1,\"t\":%llu,\"w\":%u,\"s\":\"%.12s\",\"p\":\"%.20s\",\"x\":\"%.12s\",\"n\":%d,\"g\":\"%.12s\",\"d\":\"%.20s\",\"i\":%d,\"a\":\"%.20s\",\"c\":\"%.20s\",\"h\":\"%.12s\",\"f\":\"%.12s\",\"y\":\"%.12s\",\"o\":\"%.12s\",\"r\":%u,\"q\":%d,\"b\":\"%.25s\",\"u\":\"%.36s\"}\n",
                           (unsigned long long)serializedMonotonic, serializedWall,
                           event->site, event->packageName, event->pathPrefix,
                           event->descriptionIsNew ? 1 : 0, event->state,
                           event->descriptionClass, event->viewTag, event->ancestorClass,
                           event->consumerClass, event->constructionPath, event->sourceURLForm,
                           event->proposedURLForm, event->loadOutcome,
                           event->repeat, event->installationSucceeded ? 1 : 0, buildId, uuid);
    return written > 0 && gRingPolicy.SerializedSizeFits((size_t)written);
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
    if (!installationRecord) {
        CopyRouteDetails(site, view, description, &event);
    }
    if ([packageNameOverride isKindOfClass:[NSString class]])
        CopyApproved(event.packageName, sizeof(event.packageName), packageNameOverride,
                     caml_diag::ValueKind::Package);
    CopyStateDetails(state, event.state, sizeof(event.state));
    CopyAncestorClass(view, event.ancestorClass, sizeof(event.ancestorClass));
    event.viewTag = ViewTag(view);
    event.installationRecord = installationRecord;
    event.installationSucceeded = installationSucceeded;
    os_unfair_lock_lock(&gDiagnosticLock);
    event.descriptionIsNew = DescriptionIsNewLocked(view, description);
    if (!gRingPolicy.Admit(gSessionEventCount.load(std::memory_order_relaxed))) {
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
    if (gRingPolicy.MustFlush(gRingCount) && !FlushRingLocked()) {
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
    bool flush = gRingPolicy.MustFlush(gRingCount);
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
extern "C" __attribute__((noinline, used)) void ObservePackage(__unsafe_unretained id view, __unsafe_unretained id description, const char *site) {
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
extern "C" __attribute__((noinline, used)) void ObserveState(__unsafe_unretained id view, __unsafe_unretained id state, const char *site) {
    CAMLStateContext context = { view, state, site };
    RunObserver(false, ObserveStateBody, &context);
}

struct CAMLFactoryContext { __unsafe_unretained id packageName; };
static void ObserveFactoryBody(void *rawContext) {
    CAMLFactoryContext *context = (CAMLFactoryContext *)rawContext;
    NSString *packageName = [context->packageName isKindOfClass:[NSString class]] ? context->packageName : nil;
    RecordEventBody("factory", nil, nil, nil, packageName, false, false);
}
extern "C" __attribute__((noinline, used)) void ObserveFactory(__unsafe_unretained id packageName) {
    CAMLFactoryContext context = { packageName };
    RunObserver(true, ObserveFactoryBody, &context);
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
    if (!target) return caml_diag::DecideRuntimeInstall({false, false, false, false, false}) == caml_diag::RuntimeInstallDecision::Installed;
    SEL selector = sel_registerName(site->selectorName);
    Method method = site->classMethod ? class_getClassMethod(target, selector) : class_getInstanceMethod(target, selector);
    if (!method) return caml_diag::DecideRuntimeInstall({true, false, false, false, false}) == caml_diag::RuntimeInstallDecision::Installed;
    const char *runtimeEncoding = method_getTypeEncoding(method);
    if (!ABIShapeMatches(runtimeEncoding, site->encoding))
        return caml_diag::DecideRuntimeInstall({true, true, false, false, false}) == caml_diag::RuntimeInstallDecision::Installed;
    Class hookClass = site->classMethod ? object_getClass(target) : target;
    MSHookMessageEx(hookClass, selector, site->replacement, site->original);
    return caml_diag::DecideRuntimeInstall({true, true, true, true, *site->original != NULL}) ==
           caml_diag::RuntimeInstallDecision::Installed;
}

// POD descriptors are populated synchronously by the caller before the installer sees them.
extern "C" __attribute__((noinline, used)) size_t BuildCAMLDiagnosticSites(CAMLDiagnosticSite *sites, size_t capacity) {
    if (!sites || capacity < kDiagnosticSiteCount) return 0;
    sites[0] = { "CCUIButtonModuleView", "setGlyphPackageDescription:", "v24@0:8@16", "button-package", (IMP)CAMLButtonPackageHook, &gOriginalButtonPackage, false };
    sites[1] = { "CCUIRoundButton", "setGlyphPackageDescription:", "v24@0:8@16", "round-package", (IMP)CAMLRoundPackageHook, &gOriginalRoundPackage, false };
    sites[2] = { "CCUIBaseSliderView", "setGlyphPackageDescription:", "v24@0:8@16", "slider-package", (IMP)CAMLSliderPackageHook, &gOriginalSliderPackage, false };
    sites[3] = { "CCUICAPackageDescription", "descriptionForPackageNamed:inBundle:", "@32@0:8@16@24", "factory", (IMP)CAMLFactoryHook, &gOriginalFactory, true };
    sites[4] = { "CCUIButtonModuleView", "setGlyphState:", "v24@0:8@16", "button-state", (IMP)CAMLButtonStateHook, &gOriginalButtonState, false };
    sites[5] = { "CCUIBaseSliderView", "setGlyphState:", "v24@0:8@16", "slider-state", (IMP)CAMLSliderStateHook, &gOriginalSliderState, false };
    // Verified 21D50 module seam. Getter observation is deliberately read-only:
    // it returns the exact stock result and never calls the replacement factory.
    sites[6] = { "CCUILowPowerModuleViewController", "glyphPackageDescription", "@16@0:8", "controller", (IMP)CAMLLowPowerDescriptionHook, &gOriginalLowPowerDescription, false };
    return kDiagnosticSiteCount;
}

extern "C" __attribute__((noinline, used)) void InstallCAMLDiagnosticSites(CAMLDiagnosticSite *sites, size_t count) {
    for (size_t index = 0; index < count; ++index) {
        bool succeeded = InstallSite(&sites[index]);
        RecordInstallStatus(&sites[index], succeeded);
    }
}

static void RefreshDiagnosticPreferences(void) {
    @try {
        NSString *domain = [NSString stringWithUTF8String:kDiagnosticPrefsDomain];
        NSUserDefaults *preferences = [[NSUserDefaults alloc] initWithSuiteName:domain];
        // Recorder/release choice is compile-time; only verbosity remains a
        // runtime preference in collector builds.
        gDiagnosticVerbose.store([preferences boolForKey:[NSString stringWithUTF8String:kDiagnosticVerboseKey]], std::memory_order_release);
    } @catch (...) {
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

#ifndef PLAMPYCC_CAML_DIAGNOSTIC_CORE_HPP
#define PLAMPYCC_CAML_DIAGNOSTIC_CORE_HPP

// Portable, allocation-free policy used by the production observer and by the
// native host contract.  This header deliberately contains no Objective-C or
// Darwin APIs: the hook and syscall boundaries are tested separately.
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <string_view>
#include <initializer_list>

namespace caml_diag {

enum class ValueKind { Package, State, Class };

static constexpr const char *kUnknownPackage = "unknown";
static constexpr const char *kUnknownState = "unknown-state";
static constexpr const char *kUnknownClass = "unknown-class";

static constexpr const char *kApprovedPackages[] = {
    "AirplaneMode", "Bluetooth", "Calculator", "Camera", "Flashlight",
    "Focus", "LowPower", "MusicRecognition", "Timer", "WiFi"
};
static constexpr const char *kApprovedStates[] = {
    "default", "disabled", "expanded", "highlighted", "collapsed", "off", "on", "selected"
};
static constexpr const char *kApprovedClasses[] = {
    "CCUIButtonModuleView", "CCUIButtonModuleViewController", "CCUIRoundButton",
    "CCUILabeledRoundButton", "CCUILabeledRoundButtonController", "CCUIBaseSliderView",
    "CCUICAPackageDescription", "CCUICAPackageView", "CCUIToggleModule", "CCUIAppearanceModule",
    "CCUIMuteModule", "CCUIOrientationLockModule", "CCUILowPowerModuleViewController"
};

template <size_t N>
inline const char *ApprovedValue(std::string_view value, const char * const (&allowlist)[N], const char *fallback) {
    for (const char *candidate : allowlist) {
        if (value == candidate) return candidate;
    }
    return fallback;
}

inline const char *ApprovedValue(std::string_view value, ValueKind kind) {
    switch (kind) {
        case ValueKind::Package: return ApprovedValue(value, kApprovedPackages, kUnknownPackage);
        case ValueKind::State: return ApprovedValue(value, kApprovedStates, kUnknownState);
        case ValueKind::Class: return ApprovedValue(value, kApprovedClasses, kUnknownClass);
    }
    return kUnknownClass;
}

inline bool CopyApproved(char *destination, size_t capacity, std::string_view value,
                         ValueKind kind) {
    if (!destination || capacity == 0) return false;
    const char *safe = ApprovedValue(value, kind);
    size_t length = strlen(safe);
    if (length >= capacity) length = capacity - 1;
    memcpy(destination, safe, length);
    destination[length] = '\0';
    return value == safe;
}

enum class DuplicateDecision { Accept, Repeat, Suppress };

struct DedupKey {
    const char *site;
    const char *packageName;
    const char *state;
};

class DedupPolicy {
public:
    static constexpr uint64_t kRepeatWindowMs = 100;
    static constexpr uint64_t kTupleWindowMs = 1000;

    DuplicateDecision Decide(DedupKey key, uint64_t now, bool hasPrevious, uint32_t *repeat) {
        char tuple[128] = {};
        char pair[96] = {};
        (void)snprintf_like(tuple, sizeof(tuple), key.site, key.packageName, key.state);
        (void)snprintf_like(pair, sizeof(pair), key.site, key.packageName, "");
        if (hasPrevious && strcmp(tuple, lastTuple_) == 0 && now >= lastTupleAt_ && now - lastTupleAt_ <= kTupleWindowMs) {
            lastTupleAt_ = now;
            if (repeat && now - lastTupleAtBefore_ <= kRepeatWindowMs) ++*repeat;
            lastTupleAtBefore_ = now;
            return DuplicateDecision::Repeat;
        }
        if (hasPrevious && strcmp(pair, lastPair_) == 0 && now >= lastPairAt_ && now - lastPairAt_ <= kRepeatWindowMs) {
            lastPairAt_ = now;
            lastPairAtBefore_ = now;
            if (repeat) ++*repeat;
            return DuplicateDecision::Suppress;
        }
        strncpy(lastTuple_, tuple, sizeof(lastTuple_) - 1);
        strncpy(lastPair_, pair, sizeof(lastPair_) - 1);
        lastTupleAt_ = lastTupleAtBefore_ = now;
        lastPairAt_ = lastPairAtBefore_ = now;
        return DuplicateDecision::Accept;
    }

private:
    static int snprintf_like(char *out, size_t capacity, const char *a, const char *b, const char *c) {
        if (!out || capacity == 0) return 0;
        size_t used = 0;
        for (const char *part : {a, b, c}) {
            if (!part) part = "";
            while (*part && used + 1 < capacity) out[used++] = *part++;
            if (part != c && used + 1 < capacity) out[used++] = '|';
        }
        out[used] = '\0';
        return (int)used;
    }
    char lastTuple_[128] = {};
    char lastPair_[96] = {};
    uint64_t lastTupleAt_ = 0;
    uint64_t lastTupleAtBefore_ = 0;
    uint64_t lastPairAt_ = 0;
    uint64_t lastPairAtBefore_ = 0;
};

class RingPolicy {
public:
    static constexpr size_t kCapacity = 512;
    static constexpr size_t kSerializedEventCapacity = 256;
    static constexpr uint64_t kSessionCap = 2000;

    bool Admit(uint64_t accepted) const { return accepted < kSessionCap; }
    bool SerializedSizeFits(size_t bytes) const { return bytes > 0 && bytes < kSerializedEventCapacity; }
    bool MustFlush(size_t count) const { return count >= kCapacity; }
};

// Returns the prefix ending immediately after the last complete line.  A
// partial final record is never carried into a new atomic file.
inline size_t CompleteLinePrefix(const char *bytes, size_t size) {
    if (!bytes) return 0;
    while (size > 0 && bytes[size - 1] != '\n') --size;
    return size;
}

// Retains complete records from the newest side while preserving a complete
// line boundary.  `destination` may alias neither input nor itself partially.
inline size_t RetainCompleteLines(const char *input, size_t inputSize, char *destination,
                                  size_t destinationCapacity) {
    if (!destination || destinationCapacity == 0) return 0;
    size_t complete = CompleteLinePrefix(input, inputSize);
    size_t start = complete > destinationCapacity ? complete - destinationCapacity : 0;
    while (start < complete && start > 0 && input[start - 1] != '\n') ++start;
    size_t retained = complete - start;
    if (retained > destinationCapacity) return 0;
    if (retained) memcpy(destination, input + start, retained);
    return retained;
}

enum class AtomicOperation { Open, Validate, Read, TempAcquire, Write, FileSync, Close, Rename, DirectorySync, Unlink };
enum class AtomicPhase { Initial, ExistingValidated, TempOwned, Written, Renamed, Committed, Failed };

// A small executable state machine shared by the Darwin adapter and the host
// fault matrix. It prevents a post-rename failure from pretending that the
// old file was preserved and makes temp ownership explicit on every edge.
class AtomicOutputState {
public:
    AtomicPhase phase() const { return phase_; }
    bool Apply(AtomicOperation operation) {
        switch (operation) {
            case AtomicOperation::Open: return Transition(AtomicPhase::Initial, AtomicPhase::Initial);
            case AtomicOperation::Validate: return Transition(AtomicPhase::Initial, AtomicPhase::ExistingValidated);
            case AtomicOperation::Read: return phase_ == AtomicPhase::ExistingValidated;
            case AtomicOperation::TempAcquire: return Transition(AtomicPhase::ExistingValidated, AtomicPhase::TempOwned);
            case AtomicOperation::Write: return Transition(AtomicPhase::TempOwned, AtomicPhase::Written);
            case AtomicOperation::FileSync: return phase_ == AtomicPhase::Written;
            case AtomicOperation::Close: return phase_ == AtomicPhase::Written;
            case AtomicOperation::Rename: return Transition(AtomicPhase::Written, AtomicPhase::Renamed);
            case AtomicOperation::DirectorySync: return Transition(AtomicPhase::Renamed, AtomicPhase::Committed);
            case AtomicOperation::Unlink: phase_ = AtomicPhase::Failed; return true;
        }
        return false;
    }
private:
    bool Transition(AtomicPhase expected, AtomicPhase next) {
        if (phase_ != expected) return false;
        phase_ = next;
        return true;
    }
    AtomicPhase phase_ = AtomicPhase::Initial;
};

struct PathComponents {
    const char *items[16] = {};
    size_t count = 0;
};

inline bool ParsePathComponents(const char *path, PathComponents *result) {
    if (!path || !result) return false;
    result->count = 0;
    const char *cursor = path;
    while (*cursor) {
        while (*cursor == '/') ++cursor;
        if (!*cursor) break;
        if (result->count == 16) return false;
        result->items[result->count++] = cursor;
        while (*cursor && *cursor != '/') ++cursor;
    }
    return result->count != 0;
}

enum class RuntimeInstallDecision {
    MissingClass,
    MissingMethod,
    WrongEncoding,
    HookFailed,
    OriginalUnavailable,
    Installed,
};

struct RuntimeInstallMetadata {
    bool classFound;
    bool methodFound;
    bool encodingMatches;
    bool hookSucceeded;
    bool originalAvailable;
};

inline RuntimeInstallDecision DecideRuntimeInstall(const RuntimeInstallMetadata &metadata) {
    if (!metadata.classFound) return RuntimeInstallDecision::MissingClass;
    if (!metadata.methodFound) return RuntimeInstallDecision::MissingMethod;
    if (!metadata.encodingMatches) return RuntimeInstallDecision::WrongEncoding;
    if (!metadata.hookSucceeded) return RuntimeInstallDecision::HookFailed;
    if (!metadata.originalAvailable) return RuntimeInstallDecision::OriginalUnavailable;
    return RuntimeInstallDecision::Installed;
}

} // namespace caml_diag
#endif

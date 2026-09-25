#ifndef PLAMPYCC_CAML_DIAGNOSTIC_IO_HPP
#define PLAMPYCC_CAML_DIAGNOSTIC_IO_HPP

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

namespace caml_diag {

// The production file protocol is expressed against this narrow adapter. The
// Darwin implementation supplies openat/pread/write/fsync/renameat/unlinkat;
// native tests supply a deterministic fake with the same fault points.
enum class SyscallPoint {
    EventOpen, EventValidate, EventRead, EventClose, TempOpen, TempValidate,
    Write, FileSync, TempClose, Rename, DirectorySync, TempUnlink, DirectoryCreate
};

struct SyscallAdapter {
    void *context = nullptr;
    int (*openAt)(void *, int, const char *, int, mode_t) = nullptr;
    int (*makeDirectoryAt)(void *, int, const char *, mode_t) = nullptr;
    int (*stat)(void *, int, struct stat *) = nullptr;
    ssize_t (*readAt)(void *, int, void *, size_t, off_t) = nullptr;
    ssize_t (*write)(void *, int, const void *, size_t) = nullptr;
    int (*sync)(void *, int) = nullptr;
    int (*renameAt)(void *, int, const char *, int, const char *) = nullptr;
    int (*unlinkAt)(void *, int, const char *) = nullptr;
    int (*close)(void *, int) = nullptr;
};

inline bool AdapterReady(const SyscallAdapter &adapter) {
    return adapter.openAt && adapter.makeDirectoryAt && adapter.stat && adapter.readAt &&
           adapter.write && adapter.sync && adapter.renameAt && adapter.unlinkAt && adapter.close;
}

// Owned-suffix component policy (tweak-owned zone). Every owned-suffix
// component must be owned by the effective user; the leaf must be exactly
// 0700 and intermediates must never be group/world writable. This rule is
// deliberately strict and is never weakened for platform directories: those
// are validated by ValidatePlatformPrefixDescriptor above the boundary.
inline bool ValidateDirectoryDescriptor(SyscallAdapter &adapter, int descriptor,
                                        bool leaf, uid_t effectiveUser) {
    struct stat status = {};
    if (!adapter.stat || adapter.stat(adapter.context, descriptor, &status) != 0 ||
        !S_ISDIR(status.st_mode)) return false;
    if (status.st_uid != effectiveUser) return false;
    if (leaf) return (status.st_mode & 0777) == 0700;
    return (status.st_mode & 0022) == 0;
}

// Platform-prefix policy (trusted zone). The trusted prefix is the
// platform-owned parent of the tweak-owned suffix; it is resolved once from
// an allowlisted literal with normal symlink resolution (platform-provided
// indirectness above the boundary is accepted by design). Real device chains
// are mobile:mobile 0755 or 0775 -- Apple ships group-writable mobile data
// parents -- so the mobile-owned form may be group-writable but is never
// world-writable; a root-owned prefix must have no group/world write; any
// other owner is rejected. Below the boundary every component is
// descriptor-confined with O_NOFOLLOW and validated before it becomes the
// next walk anchor, so a planted symlink or rename race cannot escape.
inline bool ValidatePlatformPrefixDescriptor(SyscallAdapter &adapter, int descriptor,
                                             uid_t effectiveUser) {
    struct stat status = {};
    if (!adapter.stat || adapter.stat(adapter.context, descriptor, &status) != 0 ||
        !S_ISDIR(status.st_mode)) return false;
    if (status.st_uid == effectiveUser) return (status.st_mode & 0002) == 0;
    if (status.st_uid == 0) return (status.st_mode & 0022) == 0;
    return false;
}

// The trusted platform prefix is opened once with normal symlink resolution
// and validated under the platform policy above. Every tweak-owned suffix
// component is then opened relative to that descriptor with O_NOFOLLOW,
// created as 0700 only when absent, and validated before it becomes the next
// walk anchor.
inline bool OpenDirectoryUnderTrustedPrefix(SyscallAdapter &adapter,
                                             const char *trustedPrefix,
                                             const char *ownedSuffix,
                                             uid_t effectiveUser,
                                             int *descriptor) {
    if (!descriptor) return false;
    *descriptor = -1;
    if (!AdapterReady(adapter) || !trustedPrefix || !ownedSuffix ||
        trustedPrefix[0] != '/' || ownedSuffix[0] == '/' || ownedSuffix[0] == '\0') return false;

    constexpr size_t kOwnedSuffixCapacity = 256;
    size_t suffixLength = 0;
    while (ownedSuffix[suffixLength] != '\0' && suffixLength < kOwnedSuffixCapacity) ++suffixLength;
    if (suffixLength == 0 || suffixLength >= kOwnedSuffixCapacity) return false;
    char suffix[kOwnedSuffixCapacity] = {};
    memcpy(suffix, ownedSuffix, suffixLength + 1);

    int current = adapter.openAt(adapter.context, AT_FDCWD, trustedPrefix,
                                 O_RDONLY | O_DIRECTORY | O_CLOEXEC, 0);
    if (current < 0) return false;
    if (!ValidatePlatformPrefixDescriptor(adapter, current, effectiveUser)) {
        adapter.close(adapter.context, current);
        return false;
    }

    char *cursor = suffix;
    for (;;) {
        while (*cursor == '/') ++cursor;
        if (*cursor == '\0') {
            adapter.close(adapter.context, current);
            return false;
        }
        char *component = cursor;
        while (*cursor != '\0' && *cursor != '/') ++cursor;
        if (*cursor == '/') {
            *cursor = '\0';
            ++cursor;
        }
        while (*cursor == '/') ++cursor;
        bool leaf = *cursor == '\0';
        if (component[0] == '\0' || strcmp(component, ".") == 0 || strcmp(component, "..") == 0) {
            adapter.close(adapter.context, current);
            return false;
        }

        int next = adapter.openAt(adapter.context, current, component,
                                  O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, 0);
        if (next < 0 && errno == ENOENT) {
            if (adapter.makeDirectoryAt(adapter.context, current, component, 0700) != 0 &&
                errno != EEXIST) {
                adapter.close(adapter.context, current);
                return false;
            }
            next = adapter.openAt(adapter.context, current, component,
                                  O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW, 0);
        }
        if (next < 0 || !ValidateDirectoryDescriptor(adapter, next, leaf, effectiveUser)) {
            if (next >= 0) adapter.close(adapter.context, next);
            adapter.close(adapter.context, current);
            return false;
        }
        if (adapter.close(adapter.context, current) != 0) {
            adapter.close(adapter.context, next);
            return false;
        }
        current = next;
        if (leaf) break;
    }

    *descriptor = current;
    return true;
}

// Tests and production share this EINTR/short-write behavior instead of
// maintaining a second write loop in a host-only verification model.
inline bool WriteAll(SyscallAdapter &adapter, int descriptor, const void *bytes, size_t length) {
    if (!AdapterReady(adapter)) return false;
    const unsigned char *cursor = static_cast<const unsigned char *>(bytes);
    while (length != 0) {
        ssize_t count = adapter.write(adapter.context, descriptor, cursor, length);
        if (count < 0) return false; // adapter retries EINTR before returning
        if (count == 0 || static_cast<size_t>(count) > length) return false;
        cursor += count;
        length -= static_cast<size_t>(count);
    }
    return true;
}

inline bool ReadAtExact(SyscallAdapter &adapter, int descriptor, void *bytes,
                        size_t length, off_t offset) {
    if (!AdapterReady(adapter)) return false;
    unsigned char *cursor = static_cast<unsigned char *>(bytes);
    size_t remaining = length;
    while (remaining != 0) {
        ssize_t count = adapter.readAt(adapter.context, descriptor, cursor, remaining, offset);
        if (count < 0) return false; // adapter retries EINTR before returning
        if (count == 0 || static_cast<size_t>(count) > remaining) return false;
        cursor += count;
        remaining -= static_cast<size_t>(count);
        offset += count;
    }
    return true;
}

} // namespace caml_diag
#endif

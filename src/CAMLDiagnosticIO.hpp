#ifndef PLAMPYCC_CAML_DIAGNOSTIC_IO_HPP
#define PLAMPYCC_CAML_DIAGNOSTIC_IO_HPP

#include <stddef.h>
#include <stdint.h>
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

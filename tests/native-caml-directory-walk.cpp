#include "../src/CAMLDiagnosticIO.hpp"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

using namespace caml_diag;

static int PosixOpenAt(void *, int directory, const char *name, int flags, mode_t mode) {
    return openat(directory, name, flags, mode);
}

static int PosixMakeDirectoryAt(void *, int directory, const char *name, mode_t mode) {
    return mkdirat(directory, name, mode);
}

static int PosixStat(void *, int descriptor, struct stat *status) {
    return fstat(descriptor, status);
}

static ssize_t PosixReadAt(void *, int descriptor, void *bytes, size_t length, off_t offset) {
    for (;;) {
        ssize_t result = pread(descriptor, bytes, length, offset);
        if (result < 0 && errno == EINTR) continue;
        return result;
    }
}

static ssize_t PosixWrite(void *, int descriptor, const void *bytes, size_t length) {
    for (;;) {
        ssize_t result = write(descriptor, bytes, length);
        if (result < 0 && errno == EINTR) continue;
        return result;
    }
}

static int PosixSync(void *, int descriptor) { return fsync(descriptor); }

static int PosixRenameAt(void *, int fromDirectory, const char *from,
                         int toDirectory, const char *to) {
    return renameat(fromDirectory, from, toDirectory, to);
}

static int PosixUnlinkAt(void *, int directory, const char *name) {
    return unlinkat(directory, name, 0);
}

static int PosixClose(void *, int descriptor) { return close(descriptor); }

static int Fail(const char *message) {
    fprintf(stderr, "FAIL: %s (errno=%d: %s)\n", message, errno, strerror(errno));
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s TRUSTED_PREFIX LEGACY_ROOT\n", argv[0]);
        return 2;
    }

    SyscallAdapter adapter = {
        nullptr, PosixOpenAt, PosixMakeDirectoryAt, PosixStat, PosixReadAt,
        PosixWrite, PosixSync, PosixRenameAt, PosixUnlinkAt, PosixClose,
    };
    constexpr const char *ownedSuffix =
        "Application Support/PlampyCC/CAML-Diagnostic";
    constexpr const char *legacySuffix =
        "var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic";

    // This is the e15e986 boundary: starting above /var and applying O_NOFOLLOW
    // to the whole path must fail at the first rootless platform symlink.
    int legacyDirectory = -1;
    if (OpenDirectoryUnderTrustedPrefix(
            adapter, argv[2], legacySuffix, geteuid(), &legacyDirectory)) {
        adapter.close(adapter.context, legacyDirectory);
        return Fail("legacy all-component no-follow walk unexpectedly crossed /var");
    }
    if (legacyDirectory != -1) return Fail("failed legacy walk leaked a descriptor");

    // Production acquires /var/jb/var/mobile/Library once with normal symlink
    // resolution, then confines only this tweak-owned suffix with O_NOFOLLOW.
    int directory = -1;
    if (!OpenDirectoryUnderTrustedPrefix(
            adapter, argv[1], ownedSuffix, geteuid(), &directory)) {
        return Fail("shared production walk did not create the owned suffix");
    }
    if (!ValidateDirectoryDescriptor(adapter, directory, true, geteuid())) {
        adapter.close(adapter.context, directory);
        return Fail("created diagnostic leaf failed shared uid/mode validation");
    }

    int events = openat(directory, "events.jsonl",
                        O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (events < 0) {
        adapter.close(adapter.context, directory);
        return Fail("events.jsonl creation failed");
    }
    constexpr char payload[] = "{\"v\":1}\n";
    if (!WriteAll(adapter, events, payload, sizeof(payload) - 1) || fsync(events) != 0) {
        adapter.close(adapter.context, events);
        adapter.close(adapter.context, directory);
        return Fail("events.jsonl write or sync failed");
    }
    struct stat eventStatus = {};
    if (fstat(events, &eventStatus) != 0 || !S_ISREG(eventStatus.st_mode) ||
        eventStatus.st_uid != geteuid() || (eventStatus.st_mode & 0777) != 0600) {
        adapter.close(adapter.context, events);
        adapter.close(adapter.context, directory);
        return Fail("events.jsonl failed uid/mode/type validation");
    }
    if (adapter.close(adapter.context, events) != 0 || fsync(directory) != 0) {
        adapter.close(adapter.context, directory);
        return Fail("events.jsonl close or directory sync failed");
    }

    events = openat(directory, "events.jsonl", O_RDONLY | O_CLOEXEC | O_NOFOLLOW, 0);
    char restored[sizeof(payload)] = {};
    if (events < 0 || !ReadAtExact(adapter, events, restored, sizeof(payload) - 1, 0) ||
        memcmp(restored, payload, sizeof(payload) - 1) != 0) {
        if (events >= 0) adapter.close(adapter.context, events);
        adapter.close(adapter.context, directory);
        return Fail("events.jsonl read-back validation failed");
    }
    if (adapter.close(adapter.context, events) != 0 ||
        adapter.close(adapter.context, directory) != 0) {
        return Fail("validated descriptors did not close cleanly");
    }

    puts("PASS: legacy symlink walk fails; trusted prefix plus hardened suffix creates and validates events.jsonl");
    return 0;
}

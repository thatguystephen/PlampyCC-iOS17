#include "../src/CAMLDiagnosticIO.hpp"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
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

// The tweak-owned suffix is strictly descriptor-confined. The legacy suffix is
// the historical all-component walk that must fail at the first platform
// symlink (/var -> /private/var, /var/jb -> relocated root).
static constexpr const char *kOwnedSuffix = "PlampyCC/CAML-Diagnostic";
static constexpr const char *kLegacySuffix =
    "var/jb/var/mobile/Library/Application Support/PlampyCC/CAML-Diagnostic";

static SyscallAdapter PosixAdapter() {
    SyscallAdapter adapter = {
        nullptr, PosixOpenAt, PosixMakeDirectoryAt, PosixStat, PosixReadAt,
        PosixWrite, PosixSync, PosixRenameAt, PosixUnlinkAt, PosixClose,
    };
    return adapter;
}

// ---------------------------------------------------------------------------
// Scenario: the e15e986 boundary. Starting above /var and applying O_NOFOLLOW
// to every component must fail at the first rootless platform symlink.
static int RunLegacyBoundary(const char *legacyRoot) {
    SyscallAdapter adapter = PosixAdapter();
    int legacyDirectory = -1;
    if (OpenDirectoryUnderTrustedPrefix(
            adapter, legacyRoot, kLegacySuffix, geteuid(), &legacyDirectory)) {
        adapter.close(adapter.context, legacyDirectory);
        return Fail("legacy all-component no-follow walk unexpectedly crossed /var");
    }
    if (legacyDirectory != -1) return Fail("failed legacy walk leaked a descriptor");
    puts("PASS: legacy all-component no-follow walk fails at the platform symlink");
    return 0;
}

// ---------------------------------------------------------------------------
// Scenario: the shared production walk must create and validate the owned
// suffix under the trusted platform prefix and round-trip events.jsonl with
// the 0600/uid file guarantees.
static int RunExpectPass(const char *trustedPrefix) {
    SyscallAdapter adapter = PosixAdapter();
    int directory = -1;
    if (!OpenDirectoryUnderTrustedPrefix(
            adapter, trustedPrefix, kOwnedSuffix, geteuid(), &directory)) {
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
    puts("PASS: trusted prefix plus hardened suffix creates and validates events.jsonl");
    return 0;
}

// ---------------------------------------------------------------------------
// Scenario: adversarial topologies must fail closed and leak no descriptor.
static int RunExpectFail(const char *trustedPrefix) {
    SyscallAdapter adapter = PosixAdapter();
    int directory = -1;
    if (OpenDirectoryUnderTrustedPrefix(
            adapter, trustedPrefix, kOwnedSuffix, geteuid(), &directory)) {
        adapter.close(adapter.context, directory);
        return Fail("adversarial topology was admitted by the production walk");
    }
    if (directory != -1) return Fail("failed adversarial walk leaked a descriptor");
    puts("PASS: adversarial topology rejected");
    return 0;
}

// ---------------------------------------------------------------------------
// Policy matrix: synthetic uid/gid/mode chains, including the exact observed
// device chain (mobile:mobile 0775 platform parent) and adversarial
// ownership/world-writable variants that a host test cannot create with real
// chown. effectiveUser 501 stands in for the on-device mobile uid.
static struct stat gFakeStatus = {};
static int gFakeStatResult = 0;

static int FakeStat(void *, int, struct stat *status) {
    if (gFakeStatResult != 0) return -1;
    *status = gFakeStatus;
    return 0;
}

struct PolicyCase {
    const char *name;
    bool platform;
    bool leaf;
    uid_t uid;
    gid_t gid;
    mode_t mode;
    bool regularOnly;
    bool expected;
};

static int RunPolicyMatrix() {
    constexpr uid_t kMobile = 501;
    constexpr gid_t kMobileGroup = 501;
    SyscallAdapter adapter = {};
    adapter.stat = FakeStat;
    static const PolicyCase cases[] = {
        // Platform-prefix policy: observed chains must be admitted.
        {"platform mobile:mobile 0755 directory admitted", true, false, kMobile, kMobileGroup, 0755, false, true},
        {"platform mobile:mobile 0775 directory admitted", true, false, kMobile, kMobileGroup, 0775, false, true},
        {"platform root:wheel 0755 directory admitted", true, false, 0, 0, 0755, false, true},
        // Adversarial platform variants must be rejected.
        {"platform world-writable directory rejected", true, false, kMobile, kMobileGroup, 0777, false, false},
        {"platform root-owned group-writable directory rejected", true, false, 0, 0, 0775, false, false},
        {"platform foreign-owned directory rejected", true, false, 502, 502, 0755, false, false},
        {"platform foreign-owned group-writable directory rejected", true, false, 502, 502, 0775, false, false},
        {"platform non-directory rejected", true, false, kMobile, kMobileGroup, 0755, true, false},
        // Owned-suffix non-leaf policy: strict, never weakened.
        {"owned intermediate euid 0700 admitted", false, false, kMobile, kMobileGroup, 0700, false, true},
        {"owned intermediate euid 0755 admitted", false, false, kMobile, kMobileGroup, 0755, false, true},
        {"owned intermediate group-writable rejected", false, false, kMobile, kMobileGroup, 0775, false, false},
        {"owned intermediate world-writable rejected", false, false, kMobile, kMobileGroup, 0777, false, false},
        {"owned intermediate root-owned rejected", false, false, 0, 0, 0755, false, false},
        {"owned intermediate foreign-owned rejected", false, false, 502, 502, 0755, false, false},
        {"owned intermediate non-directory rejected", false, false, kMobile, kMobileGroup, 0755, true, false},
        // Owned leaf policy: euid-owned, exactly 0700.
        {"owned leaf euid 0700 admitted", false, true, kMobile, kMobileGroup, 0700, false, true},
        {"owned leaf euid 0755 rejected", false, true, kMobile, kMobileGroup, 0755, false, false},
        {"owned leaf euid 0770 rejected", false, true, kMobile, kMobileGroup, 0770, false, false},
        {"owned leaf root-owned rejected", false, true, 0, 0, 0700, false, false},
        {"owned leaf foreign-owned rejected", false, true, 502, 502, 0700, false, false},
    };
    for (const PolicyCase &test : cases) {
        memset(&gFakeStatus, 0, sizeof(gFakeStatus));
        gFakeStatResult = 0;
        gFakeStatus.st_uid = test.uid;
        gFakeStatus.st_gid = test.gid;
        gFakeStatus.st_mode = test.regularOnly ? S_IFREG : S_IFDIR;
        gFakeStatus.st_mode |= test.mode & 0777;
        bool result = test.platform
            ? ValidatePlatformPrefixDescriptor(adapter, 7, kMobile)
            : ValidateDirectoryDescriptor(adapter, 7, test.leaf, kMobile);
        if (result != test.expected) {
            fprintf(stderr, "FAIL: policy matrix: %s (got %d, want %d)\n",
                    test.name, result ? 1 : 0, test.expected ? 1 : 0);
            return 1;
        }
    }
    memset(&gFakeStatus, 0, sizeof(gFakeStatus));
    gFakeStatResult = -1;
    if (ValidatePlatformPrefixDescriptor(adapter, 7, kMobile) ||
        ValidateDirectoryDescriptor(adapter, 7, false, kMobile) ||
        ValidateDirectoryDescriptor(adapter, 7, true, kMobile)) {
        return Fail("policy matrix admitted a descriptor whose stat failed");
    }
    gFakeStatResult = 0;
    puts("PASS: policy matrix admits the observed mobile:mobile chains and rejects adversarial ownership/mode variants");
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "policy-matrix") == 0) return RunPolicyMatrix();
    if (argc == 3 && strcmp(argv[1], "legacy-boundary") == 0) return RunLegacyBoundary(argv[2]);
    if (argc == 3 && strcmp(argv[1], "expect-pass") == 0) return RunExpectPass(argv[2]);
    if (argc == 3 && strcmp(argv[1], "expect-fail") == 0) return RunExpectFail(argv[2]);
    fprintf(stderr,
            "usage: %s policy-matrix | legacy-boundary LEGACY_ROOT | "
            "expect-pass TRUSTED_PREFIX | expect-fail TRUSTED_PREFIX\n", argv[0]);
    return 2;
}

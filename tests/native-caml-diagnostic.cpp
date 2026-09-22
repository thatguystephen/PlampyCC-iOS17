#include "../src/CAMLDiagnosticCore.hpp"
#include "../src/CAMLDiagnosticIO.hpp"
#include <assert.h>
#include <string.h>

using namespace caml_diag;

static void TestApprovedValues() {
    assert(strcmp(ApprovedValue("WiFi", ValueKind::Package), "WiFi") == 0);
    assert(strcmp(ApprovedValue("user-controlled", ValueKind::Package), "unknown") == 0);
    char state[16] = {};
    assert(CopyApproved(state, sizeof(state), "selected", ValueKind::State));
    assert(strcmp(state, "selected") == 0);
    assert(!CopyApproved(state, sizeof(state), "private", ValueKind::State));
    assert(strcmp(state, "unknown-state") == 0);
}

static void TestDedupPolicy() {
    DedupPolicy policy;
    uint32_t repeat = 0;
    assert(policy.Decide({"button", "WiFi", "on"}, 10, false, &repeat) == DuplicateDecision::Accept);
    assert(policy.Decide({"button", "WiFi", "on"}, 50, true, &repeat) == DuplicateDecision::Repeat);
    assert(policy.Decide({"button", "WiFi", "off"}, 80, true, &repeat) == DuplicateDecision::Suppress);
    assert(policy.Decide({"button", "WiFi", "on"}, 1200, true, &repeat) == DuplicateDecision::Accept);
}

static void TestRetention() {
    const char input[] = "old\npartial";
    char retained[32] = {};
    size_t bytes = RetainCompleteLines(input, strlen(input), retained, sizeof(retained));
    assert(bytes == 4 && memcmp(retained, "old\n", 4) == 0);
    const char many[] = "one\ntwo\nthree\n";
    memset(retained, 0, sizeof(retained));
    bytes = RetainCompleteLines(many, strlen(many), retained, 8);
    assert(bytes == 6 && memcmp(retained, "three\n", 6) == 0);
}

struct FakeWriter {
    size_t calls = 0;
    size_t bytes = 0;
    const char *source = "abcdef";
};

static int FakeOpen(void *, int, const char *, int, mode_t) { return 1; }
static int FakeMkdir(void *, int, const char *, mode_t) { return 0; }
static int FakeStat(void *, int, struct stat *status) {
    memset(status, 0, sizeof(*status));
    status->st_mode = S_IFREG | 0600;
    return 0;
}
static ssize_t FakeRead(void *raw, int, void *destination, size_t length, off_t offset) {
    FakeWriter *reader = static_cast<FakeWriter *>(raw);
    size_t amount = length > 2 ? 2 : length;
    memcpy(destination, reader->source + offset, amount);
    return static_cast<ssize_t>(amount);
}
static ssize_t FakeWrite(void *raw, int, const void *, size_t length) {
    FakeWriter *writer = static_cast<FakeWriter *>(raw);
    ++writer->calls;
    size_t amount = length > 2 ? 2 : length;
    writer->bytes += amount;
    return static_cast<ssize_t>(amount);
}
static int FakeSync(void *, int) { return 0; }
static int FakeRename(void *, int, const char *, int, const char *) { return 0; }
static int FakeUnlink(void *, int, const char *) { return 0; }
static int FakeClose(void *, int) { return 0; }

static void TestInjectedSyscallAdapter() {
    FakeWriter writer;
    SyscallAdapter adapter = {&writer, FakeOpen, FakeMkdir, FakeStat, FakeRead,
                              FakeWrite, FakeSync, FakeRename, FakeUnlink, FakeClose};
    const char payload[] = "abcdef";
    assert(WriteAll(adapter, 1, payload, 6));
    assert(writer.bytes == 6 && writer.calls == 3);
    char restored[7] = {};
    assert(ReadAtExact(adapter, 1, restored, 6, 0));
    assert(strcmp(restored, payload) == 0);
    assert(WriteAll(adapter, 1, payload, 0));
    assert(ReadAtExact(adapter, 1, restored, 0, 0));
    SyscallAdapter incomplete = adapter;
    incomplete.stat = nullptr;
    assert(!AdapterReady(incomplete));
    assert(!WriteAll(incomplete, 1, payload, 1));
}

static void TestRuntimeInstallDecision() {
    assert(DecideRuntimeInstall({true, true, true, true, true}) == RuntimeInstallDecision::Installed);
    assert(DecideRuntimeInstall({false, false, false, false, false}) == RuntimeInstallDecision::MissingClass);
    assert(DecideRuntimeInstall({true, false, false, false, false}) == RuntimeInstallDecision::MissingMethod);
    assert(DecideRuntimeInstall({true, true, false, false, false}) == RuntimeInstallDecision::WrongEncoding);
    assert(DecideRuntimeInstall({true, true, true, false, false}) == RuntimeInstallDecision::HookFailed);
    assert(DecideRuntimeInstall({true, true, true, true, false}) == RuntimeInstallDecision::OriginalUnavailable);
}

static void TestAtomicFaultBoundary() {
    AtomicOutputState state;
    assert(state.Apply(AtomicOperation::Open));
    assert(!state.Apply(AtomicOperation::Write));
    assert(!state.Apply(AtomicOperation::Rename));
    assert(state.Apply(AtomicOperation::Validate));
    assert(state.Apply(AtomicOperation::Read));
    assert(!state.Apply(AtomicOperation::FileSync));
    assert(state.Apply(AtomicOperation::TempAcquire));
    assert(state.Apply(AtomicOperation::Write));
    assert(state.Apply(AtomicOperation::FileSync));
    assert(state.Apply(AtomicOperation::Close));
    assert(state.Apply(AtomicOperation::Rename));
    assert(!state.Apply(AtomicOperation::Write));
    assert(state.Apply(AtomicOperation::DirectorySync));
    assert(state.phase() == AtomicPhase::Committed);

    AtomicOutputState failed;
    assert(failed.Apply(AtomicOperation::Open));
    assert(failed.Apply(AtomicOperation::Validate));
    assert(failed.Apply(AtomicOperation::TempAcquire));
    assert(failed.Apply(AtomicOperation::Unlink));
    assert(failed.phase() == AtomicPhase::Failed);
    assert(!failed.Apply(AtomicOperation::Rename));

    PathComponents path;
    char mutablePath[] = "//var///mobile/Library";
    assert(ParsePathComponents(mutablePath, &path));
    assert(path.count == 3 && strcmp(path.items[0], "var///mobile/Library") == 0);
    assert(!ParsePathComponents("////", &path));
}

int main() {
    TestApprovedValues();
    TestDedupPolicy();
    TestRetention();
    TestInjectedSyscallAdapter();
    TestRuntimeInstallDecision();
    TestAtomicFaultBoundary();
    return 0;
}

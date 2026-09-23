#include "../src/CAMLDiagnosticCore.hpp"
#include "../src/CAMLDiagnosticIO.hpp"
#include "../src/CAMLReplacementCore.hpp"
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

static void TestReplacementRouting() {
    using namespace caml_replacement;
    // Exact-name map route (verified sub_8c98 mechanism).
    assert(strcmp(BundleDirectoryForPackage("timer", Site::Setter, 0), "TimerModule.bundle") == 0);
    assert(BundleDirectoryForPackage("timer", Site::Setter, 1) == nullptr); // verified timer+Pulsar skip
    assert(strcmp(BundleDirectoryForPackage("WiFi", Site::Setter, 0), "ConnectivityModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("Bluetooth", Site::Setter, 1), "ConnectivityModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("StyleMode", Site::Setter, 0), "AppearanceModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("Ringer-Leading-D73", Site::Setter, 0), "SpringBoard.framework") == 0);
    assert(strcmp(BundleDirectoryForPackage("Ringer-Minimal-D73", Site::Setter, 1), "SpringBoard.framework") == 0);
    assert(strcmp(BundleDirectoryForPackage("Mute", Site::Setter, 0), "MuteModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("dnd_cg_02", Site::Setter, 0), "FocusUI.framework") == 0);
    assert(strcmp(BundleDirectoryForPackage("MPAVScreenMirroring", Site::Setter, 0), "AirPlayMirroringModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("replaykit-v2", Site::Setter, 0), "ReplayKitModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("HAE_1_x_1", Site::Setter, 1), "HearingAidsModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("Brightness", Site::Setter, 0), "DisplayModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("Volume", Site::Setter, 0), "MediaControls.framework") == 0);
    // Fail-open on dictionary-miss semantics and empty identity.
    assert(BundleDirectoryForPackage("unknown-package", Site::Setter, 0) == nullptr);
    assert(BundleDirectoryForPackage("timer1", Site::Setter, 0) == nullptr);
    assert(BundleDirectoryForPackage("", Site::Setter, 0) == nullptr);
    // Verified slider containsString: route (sub_93cc) and its fail-open miss.
    assert(strcmp(BundleDirectoryForPackage("Brightness", Site::Slider, 0), "DisplayModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("BrightnessControl", Site::Slider, 1), "DisplayModule.bundle") == 0);
    assert(strcmp(BundleDirectoryForPackage("Volume", Site::Slider, 0), "MediaControls.framework") == 0);
    assert(strcmp(BundleDirectoryForPackage("Ringer-Volume-D73", Site::Slider, 1), "MediaControls.framework") == 0);
    assert(BundleDirectoryForPackage("WiFi", Site::Slider, 0) == nullptr);
    assert(BundleDirectoryForPackage("", Site::Slider, 0) == nullptr);
    // Table shape: unique names, non-empty bundle directories.
    for (size_t i = 0; i < kPackageBundleCount; ++i) {
        assert(kPackageBundles[i].packageName[0] != '\0');
        assert(kPackageBundles[i].bundleDirectory[0] != '\0');
        for (size_t j = i + 1; j < kPackageBundleCount; ++j)
            assert(strcmp(kPackageBundles[i].packageName, kPackageBundles[j].packageName) != 0);
    }
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

// SP1: live preference reconciliation across the three verified setter seams.
// Production-coupled: drives the same decision helpers the ARC reconcile pass
// runs (ClassifyInstall/DecideReconcile) and the same routing map the factory
// attempts (BundleDirectoryForPackage through RoutingSiteFor). The stateful
// record/reconcile transitions themselves are exercised in
// TestPackageRecoveryTransitions below against the production policy.
//
// Consumer destruction is a registry-lifetime property rather than a decision:
// the weak NSHashTable drops destroyed consumers before the pass ever gathers
// facts, so destruction yields "no facts, no action" (structural contract in
// tests/static-check.ts and tests/caml-diagnostic-contract.py; Foundation
// weak-lifetime behavior is not executed on this host).
static void TestPackageReconcileTransitions() {
    using namespace caml_replacement;
    // Read-back classification distinguishes owned/applied replacements from
    // untouched and newer stock descriptions.
    assert(ClassifyInstall(true, true, false) == InstallObservation::OwnedReplacement);
    assert(ClassifyInstall(true, true, true) == InstallObservation::OwnedReplacement);
    assert(ClassifyInstall(true, false, true) == InstallObservation::StockUnchanged);
    assert(ClassifyInstall(true, false, false) == InstallObservation::StockChanged);
    assert(ClassifyInstall(false, false, false) == InstallObservation::NoDescription);

    struct SeamCase { Seam seam; const char *stem; };
    const SeamCase seams[] = {
        {Seam::ButtonPackage, "WiFi"},
        {Seam::RoundPackage, "Bluetooth"},
        {Seam::SliderPackage, "BrightnessControl"},
    };
    for (const SeamCase &seamCase : seams) {
        Site site = RoutingSiteFor(seamCase.seam);
        // The factory attempt is the resource-availability probe: routing hit
        // plus a present theme resource.
        auto available = [&](int theme, bool resourcePresent) {
            return resourcePresent && BundleDirectoryForPackage(seamCase.stem, site, theme) != nullptr;
        };
        // Disabled startup leaves stock untouched; enabling reconciles it.
        assert(DecideReconcile({false, available(0, true), InstallObservation::StockUnchanged, false}) == ReconcileAction::KeepInstalled);
        assert(DecideReconcile({true, available(0, true), InstallObservation::StockUnchanged, false}) == ReconcileAction::ApplyReplacement);
        // Plampy<->Pulsar theme change while owned: swap, then idempotent.
        assert(DecideReconcile({true, available(1, true), InstallObservation::OwnedReplacement, false}) == ReconcileAction::ApplyReplacement);
        assert(DecideReconcile({true, available(1, true), InstallObservation::OwnedReplacement, true}) == ReconcileAction::KeepInstalled);
        // Disable restores the preserved original; re-enable themes again.
        assert(DecideReconcile({false, false, InstallObservation::OwnedReplacement, true}) == ReconcileAction::RestoreStock);
        assert(DecideReconcile({true, available(0, true), InstallObservation::StockUnchanged, false}) == ReconcileAction::ApplyReplacement);
        // Missing or unsupported resources: restore when owned, keep stock otherwise.
        assert(DecideReconcile({true, available(0, false), InstallObservation::OwnedReplacement, true}) == ReconcileAction::RestoreStock);
        assert(DecideReconcile({true, available(0, false), InstallObservation::StockUnchanged, false}) == ReconcileAction::KeepInstalled);
        // Newer stock assignment: never overwritten while not owning it;
        // themed again (adopting it as the recovery original) only when enabled.
        assert(DecideReconcile({false, false, InstallObservation::StockChanged, false}) == ReconcileAction::KeepInstalled);
        assert(DecideReconcile({true, available(0, true), InstallObservation::StockChanged, false}) == ReconcileAction::ApplyReplacement);
        assert(DecideReconcile({true, available(0, false), InstallObservation::StockChanged, false}) == ReconcileAction::KeepInstalled);
        // Nothing installed: untouched in every state.
        assert(DecideReconcile({true, available(0, true), InstallObservation::NoDescription, false}) == ReconcileAction::KeepInstalled);
        assert(DecideReconcile({false, false, InstallObservation::NoDescription, true}) == ReconcileAction::KeepInstalled);
    }

    // Seam-coupled routing: slider stems route only at the slider seam and the
    // exact-name map never accepts them elsewhere (factory fail-open).
    assert(RoutingSiteFor(Seam::SliderPackage) == Site::Slider);
    assert(RoutingSiteFor(Seam::ButtonPackage) == Site::Setter);
    assert(RoutingSiteFor(Seam::RoundPackage) == Site::Setter);
    assert(BundleDirectoryForPackage("BrightnessControl", RoutingSiteFor(Seam::SliderPackage), 1) != nullptr);
    assert(BundleDirectoryForPackage("BrightnessControl", RoutingSiteFor(Seam::ButtonPackage), 1) == nullptr);
    // Unsupported resource per theme: timer under Pulsar restores owned state
    // at the mapped seams but is supported under Plampy.
    assert(BundleDirectoryForPackage("timer", RoutingSiteFor(Seam::ButtonPackage), 1) == nullptr);
    assert(BundleDirectoryForPackage("timer", RoutingSiteFor(Seam::RoundPackage), 1) == nullptr);
    assert(BundleDirectoryForPackage("timer", RoutingSiteFor(Seam::ButtonPackage), 0) != nullptr);
    assert(DecideReconcile({true, false, InstallObservation::OwnedReplacement, false}) == ReconcileAction::RestoreStock);
}

// ---- SP1-R1/SP1-R2: stateful owned-description recovery transitions ----
//
// These drive the PRODUCTION transitions (the exact caml_replacement functions
// src/CAMLReplacement.xm delegates to) over opaque description handles with
// injected boundaries: identity equality, the owned-marker predicate that
// mirrors the adapter's marker on constructed replacements, and a fake
// factory/setter pair. Assertions are on handle IDENTITY (original and
// preserved-original object identity), not just decision enums, so owned
// re-assignment can never silently lose the real stock object again.
//
// Honest limitation: this is policy-level coverage over opaque handles.
// Foundation object lifetimes (associated-object teardown, NSHashTable weak
// zeroing on consumer destruction) are NOT executed on this host and no
// weak-lifetime proof is claimed from this model; the destruction boundary is
// structural in the adapter (weak registry + association-scoped records) and
// source-checked in tests/static-check.ts and tests/caml-diagnostic-contract.py.
// What is asserted here is the policy-level destruction contract: a consumer
// with no record and nothing installed produces no setter invocation and keeps
// no record from which a stale restore could be resurrected.
namespace {

using caml_replacement::DescriptionHandle;

struct FakeDescription {
    const char *stem;
    int tag;
};

// Stand-in description identities. S1/S2 are genuine stock descriptions (never
// marked owned); T1/T2/U1/U2 stand in for replacements the fake factory
// constructs and marks, exactly like production output. T1Copy is a distinct
// object equal to T1 by value (the adapter's isEqual: fallback case).
FakeDescription S1 = {"WiFi", 1};
FakeDescription S2 = {"WiFi", 2};
FakeDescription T1 = {"WiFi", 11};
FakeDescription T2 = {"WiFi", 12};
FakeDescription U1 = {"WiFi", 21};
FakeDescription U2 = {"WiFi", 22};
FakeDescription T1Copy = {"WiFi", 13};

DescriptionHandle H(const FakeDescription *description) {
    return static_cast<DescriptionHandle>(description);
}

bool FakeEqual(DescriptionHandle left, DescriptionHandle right) { return left == right; }

// Mirrors SameDescription's isEqual: fallback for the value-equality case.
bool FakeValueEqual(DescriptionHandle left, DescriptionHandle right) {
    if (left == right) return true;
    if (!left || !right) return false;
    return strcmp(static_cast<const FakeDescription *>(left)->stem,
                  static_cast<const FakeDescription *>(right)->stem) == 0;
}

// The owned-marker predicate: the fakes the factory "constructs" are marked
// for good, exactly like the marker association production sets on its output.
bool FakeOwned(DescriptionHandle handle) {
    return handle == H(&T1) || handle == H(&T2) || handle == H(&U1) || handle == H(&U2);
}

// Fake consumer: the shim's install path and the ARC reconcile pass sequenced
// exactly as src/CAMLReplacement.xm sequences them, with only the boundaries
// faked (construction result, original setter storage). All classification,
// recording and planning is the production policy.
struct FakeConsumer {
    bool hasState = false;
    caml_replacement::RecoveryState state = caml_replacement::NoRecoveryState();
    DescriptionHandle installed = nullptr; // glyphPackageDescription read-back result
    int seam = 0;
    int theme = 0;

    DescriptionHandle Install(DescriptionHandle incoming, DescriptionHandle factoryResult) {
        caml_replacement::ConstructionPlan construction = caml_replacement::PlanConstruction(
            state, hasState, incoming, theme, FakeEqual, FakeOwned);
        DescriptionHandle replacement = construction.keepOwned ? nullptr : factoryResult;
        DescriptionHandle argument = replacement ? replacement : incoming;
        installed = argument; // the fake original setter stores its argument
        state = caml_replacement::RecordInstall(
            caml_replacement::InstallInput{state, hasState, incoming, argument,
                                           replacement != nullptr, theme, seam},
            FakeEqual, FakeOwned);
        hasState = true;
        return argument;
    }

    caml_replacement::ReconcilePlan Reconcile(bool enabled, DescriptionHandle desired) {
        caml_replacement::ReconcileObservation observed = caml_replacement::ObserveReconcile(
            state, hasState, installed, installed != nullptr, FakeEqual);
        caml_replacement::ReconcilePlan plan = caml_replacement::PlanReconcileAction(
            observed.base, observed.kind, installed, enabled, desired, theme, seam, FakeEqual);
        if (plan.perform) installed = plan.invoke; // the fake original setter
        if (plan.clear) {
            state = caml_replacement::NoRecoveryState();
            hasState = false;
        } else {
            state = plan.next;
            hasState = true;
        }
        return plan;
    }
};

} // namespace

static void TestPackageRecoveryTransitions() {
    using namespace caml_replacement;
    // Construction-side classification: what the factory builds from, and when
    // an owned input is kept as-is instead of rebuilt.
    {
        RecoveryState owned{H(&S1), H(&T1), 0};
        ConstructionPlan plan = PlanConstruction(owned, true, H(&S1), 0, FakeEqual, FakeOwned);
        assert(!plan.keepOwned && plan.source == H(&S1)); // stock input builds from itself
        plan = PlanConstruction(owned, true, H(&T1), 0, FakeEqual, FakeOwned);
        assert(plan.keepOwned && plan.source == H(&S1)); // current owned input is kept
        plan = PlanConstruction(owned, true, H(&T1), 1, FakeEqual, FakeOwned);
        assert(!plan.keepOwned && plan.source == H(&S1)); // theme change rebuilds from S1
        plan = PlanConstruction(owned, true, H(&U2), 0, FakeEqual, FakeOwned);
        assert(!plan.keepOwned && plan.source == H(&S1)); // stale owned input still from S1
        plan = PlanConstruction(NoRecoveryState(), false, H(&S1), 0, FakeEqual, FakeOwned);
        assert(!plan.keepOwned && plan.source == H(&S1));
        plan = PlanConstruction(NoRecoveryState(), false, H(&T1), 0, FakeEqual, FakeOwned);
        assert(!plan.keepOwned && plan.source == H(&T1)); // owned without record: not stock
        assert(ClassifyIncoming(NoRecoveryState(), false, H(&T1), FakeEqual, FakeOwned) ==
               IncomingKind::OwnedReplacement);
        assert(ClassifyIncoming(NoRecoveryState(), false, H(&S2), FakeEqual, FakeOwned) ==
               IncomingKind::NewStock);
        // Value equality (the adapter's isEqual: fallback) classifies a
        // distinct but equal object as the owned replacement as well.
        assert(ClassifyIncoming(owned, true, H(&T1Copy), FakeValueEqual, FakeOwned) ==
               IncomingKind::OwnedReplacement);
        RecoveryState next = RecordInstall(
            InstallInput{owned, true, H(&T1Copy), H(&U1), true, 1, 0}, FakeValueEqual, FakeOwned);
        assert(next.original == H(&S1) && next.applied == H(&U1) && next.appliedTheme == 1);
    }

    const int seams[] = {(int)Seam::ButtonPackage, (int)Seam::RoundPackage,
                         (int)Seam::SliderPackage};
    for (int seam : seams) {
        // SP1-R1 regression: owned re-assignment preserves the real stock.
        // S1->T1 owned install, then T1 re-assigned through the same seam
        // (kept as-is while current, rebuilt as U1 after a theme change);
        // disable must restore S1 — never a themed description.
        {
            FakeConsumer h; h.seam = seam;
            assert(h.Install(H(&S1), H(&T1)) == H(&T1));
            assert(h.state.original == H(&S1) && h.state.applied == H(&T1));
            assert(h.Install(H(&T1), nullptr) == H(&T1)); // keep-owned re-assignment
            assert(h.state.original == H(&S1) && h.state.applied == H(&T1));
            h.theme = 1;
            assert(h.Install(H(&T1), H(&U1)) == H(&U1)); // rebuild for the new theme
            assert(h.state.original == H(&S1));          // S1 preserved — never T1
            assert(h.state.applied == H(&U1) && h.state.appliedTheme == 1);
            ReconcilePlan plan = h.Reconcile(false, nullptr); // disable
            assert(plan.action == ReconcileAction::RestoreStock);
            assert(plan.seam == seam && plan.perform && plan.invoke == H(&S1));
            // SP1-R3: restoration preserves the stock recovery record
            // (original, nil) instead of clearing it.
            assert(!plan.clear && h.installed == H(&S1));
            assert(h.state.original == H(&S1) && h.state.applied == nullptr);
        }
        // SP1-R1 regression: a reconstruction miss on an owned re-assignment
        // must not drop ownership — disable still restores the real stock.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            h.Install(H(&T1), nullptr); // factory/resource miss: T1 passes through
            assert(h.state.original == H(&S1) && h.state.applied == H(&T1));
            assert(h.state.appliedTheme == 0);
            ReconcilePlan plan = h.Reconcile(false, nullptr);
            assert(plan.action == ReconcileAction::RestoreStock && plan.invoke == H(&S1));
        }
        // SP1-R1 regression: owned re-assignment followed by a missing
        // resource restores the real stock rather than keeping the override.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            h.theme = 1;
            h.Install(H(&T1), H(&U1));
            ReconcilePlan plan = h.Reconcile(true, nullptr); // enabled, resource miss
            assert(plan.action == ReconcileAction::RestoreStock && plan.invoke == H(&S1));
        }
        // SP1-R1 regression: owned re-assignment followed by a theme change
        // swaps the replacement (preserving the original), and disable then
        // restores the real stock.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            h.theme = 1;
            ReconcilePlan plan = h.Reconcile(true, H(&U2)); // Plampy -> Pulsar
            assert(plan.action == ReconcileAction::ApplyReplacement && plan.invoke == H(&U2));
            assert(h.state.original == H(&S1) && h.state.applied == H(&U2));
            assert(h.state.appliedTheme == 1);
            plan = h.Reconcile(false, nullptr);
            assert(plan.invoke == H(&S1));
        }
        // Genuinely newer stock (including through the seam) is adopted as the
        // recovery original and never overwritten; ownership follows reality.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            h.Install(H(&S2), H(&T2)); // newer stock S2 through the seam
            assert(h.state.original == H(&S2) && h.state.applied == H(&T2));
            ReconcilePlan plan = h.Reconcile(false, nullptr);
            assert(plan.invoke == H(&S2)); // restores the newer stock
            FakeConsumer g; g.seam = seam;
            g.Install(H(&S1), H(&T1));
            g.Install(H(&S2), nullptr); // newer stock passes through on a miss
            assert(g.state.original == H(&S2) && g.state.applied == nullptr);
            ReconcilePlan p2 = g.Reconcile(false, nullptr);
            assert(p2.action == ReconcileAction::KeepInstalled && !p2.perform);
            assert(g.installed == H(&S2));
        }
        // Disabled startup leaves stock untouched; enabling themes the
        // preserved stock under its own identity.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), nullptr); // disabled: stock passes through
            assert(h.state.original == H(&S1) && h.state.applied == nullptr);
            ReconcilePlan plan = h.Reconcile(false, nullptr);
            assert(plan.action == ReconcileAction::KeepInstalled && !plan.perform);
            plan = h.Reconcile(true, H(&T1));
            assert(plan.action == ReconcileAction::ApplyReplacement && plan.invoke == H(&T1));
            assert(h.state.original == H(&S1) && h.state.applied == H(&T1));
        }
        // Disable restores the preserved stock, drops ownership, and keeps the
        // stock record; re-enable re-themes the restored stock under its own
        // identity again.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            ReconcilePlan plan = h.Reconcile(false, nullptr);
            assert(plan.action == ReconcileAction::RestoreStock && plan.invoke == H(&S1));
            plan = h.Reconcile(true, H(&T2));
            assert(plan.action == ReconcileAction::ApplyReplacement && plan.invoke == H(&T2));
            assert(h.state.original == H(&S1) && h.state.applied == H(&T2));
        }
        // SP1-R3 regression: restore -> stale owned re-assignment -> DISABLED
        // reconcile. Restoration preserved the stock record, so the stale
        // owned pass-through re-records against the preserved stock and the
        // next disabled reconcile restores the real original S again — a
        // themed description can never remain installed while the tweak is
        // disabled when the stock was known.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1)); // (S1, T1, 0)
            ReconcilePlan plan = h.Reconcile(false, nullptr); // disable: restore S1
            assert(plan.action == ReconcileAction::RestoreStock && plan.perform);
            assert(plan.invoke == H(&S1) && h.installed == H(&S1)); // S identity
            assert(!plan.clear && h.state.original == H(&S1) && h.state.applied == nullptr);
            // While still disabled, the retained owned T1 is re-assigned
            // through the seam: the factory misses (disabled), T1 passes
            // through, and recording must keep the preserved stock.
            assert(h.Install(H(&T1), nullptr) == H(&T1));
            assert(h.state.original == H(&S1)); // preserved stock — never nullptr
            assert(h.state.applied == H(&T1));  // ownership survives the miss
            plan = h.Reconcile(false, nullptr); // disabled reconcile
            assert(plan.action == ReconcileAction::RestoreStock && plan.perform);
            assert(plan.invoke == H(&S1) && h.installed == H(&S1)); // S identity
            assert(!plan.clear && h.state.original == H(&S1) && h.state.applied == nullptr);
        }
        // SP1-R3 regression: restore -> stale owned re-assignment -> RE-ENABLE.
        // Re-enabling rebuilds from the preserved stock original (never from
        // the stale owned replacement) and restores S identity in the record.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            ReconcilePlan plan = h.Reconcile(false, nullptr); // disable: restore S1
            assert(plan.invoke == H(&S1) && h.installed == H(&S1));
            assert(h.Install(H(&T1), nullptr) == H(&T1)); // stale owned re-assign
            assert(h.state.original == H(&S1) && h.state.applied == H(&T1));
            ConstructionPlan build =
                PlanConstruction(h.state, h.hasState, H(&T1), h.theme, FakeEqual, FakeOwned);
            assert(!build.keepOwned && build.source == H(&S1)); // rebuild from S1
            plan = h.Reconcile(true, H(&U1)); // re-enable
            assert(plan.action == ReconcileAction::ApplyReplacement && plan.perform);
            assert(plan.invoke == H(&U1));
            assert(h.state.original == H(&S1) && h.state.applied == H(&U1));
        }
        // A stale owned replacement re-assigned later (marker-owned, record
        // already on another replacement or gone) is never "genuinely newer
        // stock": it never becomes the recovery original.
        {
            FakeConsumer h; h.seam = seam;
            h.Install(H(&S1), H(&T1));
            h.theme = 1;
            h.Install(H(&T1), H(&U1)); // (S1, U1, 1)
            h.Install(H(&T1), H(&U2)); // stale T1 re-assigned
            assert(h.state.original == H(&S1)); // T1 never recorded as stock
            assert(h.state.applied == H(&U2));
            ReconcilePlan plan = h.Reconcile(false, nullptr);
            assert(plan.invoke == H(&S1));
            FakeConsumer g; g.seam = seam;
            g.Install(H(&T1), nullptr); // marked input with no record at all
            assert(g.state.original == nullptr); // fail open: no stock is known
            assert(g.state.applied == H(&T1));   // ownership not silently dropped
            ReconcilePlan p2 = g.Reconcile(false, nullptr);
            // Owned with unknown original (the stock was never known here —
            // the post-restore variant keeps its record, see the SP1-R3
            // blocks above): fail open, keep installed, and never "restore" a
            // themed description as stock.
            assert(p2.action == ReconcileAction::KeepInstalled && !p2.perform);
            assert(g.installed == H(&T1) && g.state.applied == H(&T1));
        }
        // Destruction boundary (policy level, honest): consumer destruction
        // releases the record and drops the weak-registry entry before any
        // pass — that teardown is Foundation runtime behavior NOT executed on
        // this host, and no weak-lifetime proof is claimed from this model.
        // Policy contract: with no record and nothing installed (or the
        // description gone), the production transitions issue no setter
        // invocation, clear the record, and cannot resurrect a stale restore.
        {
            FakeConsumer h; h.seam = seam;
            ReconcilePlan plan = h.Reconcile(true, H(&T1));
            assert(!plan.perform && plan.clear && plan.seam == seam);
            assert(h.state.original == nullptr && h.state.applied == nullptr);
            assert(ObserveReconcile(NoRecoveryState(), false, nullptr, false, FakeEqual).kind ==
                   InstallObservation::NoDescription);
            FakeConsumer g; g.seam = seam;
            g.Install(H(&S1), H(&T1));
            g.installed = nullptr; // the consumer's description is gone
            plan = g.Reconcile(true, H(&T1));
            assert(!plan.perform && plan.clear);
        }
    }
}

int main() {
    TestApprovedValues();
    TestDedupPolicy();
    TestRetention();
    TestInjectedSyscallAdapter();
    TestRuntimeInstallDecision();
    TestReplacementRouting();
    TestAtomicFaultBoundary();
    TestPackageReconcileTransitions();
    TestPackageRecoveryTransitions();
    return 0;
}

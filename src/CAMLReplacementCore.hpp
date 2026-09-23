#ifndef PLAMPYCC_CAML_REPLACEMENT_CORE_HPP
#define PLAMPYCC_CAML_REPLACEMENT_CORE_HPP

// Pure routing policy for the verified construct-and-pass CAML route.
// Evidence: evidence/CAML-ABI-MAP-21D50.md §1.7 and §3, and
// evidence/caml-static/orig-hook-map.md (original sub_8c98 / sub_93cc flows).
//
// The original routed by NSConstantDictionary lookup (button/round sites) or
// containsString: dispatch (slider site), then built
// "<theme>/Assets/<mapped-bundle>" and passed the ORIGINAL package name to
// -[CCUICAPackageDescription initWithPackageName:inBundle:]. The original
// dictionary contents were never enumerated from the blob (ABI map §6.1);
// this table is reconstructed from the shipped theme package inventory
// (each mapped bundle directory really contains "<name>.ca") cross-checked
// against the original binary's string inventory. Every name outside the
// table fails open exactly like the original dictionary miss.
//
// This header is deliberately free of Objective-C and Darwin APIs so the
// production decision logic is exercised by tests/native-caml-diagnostic.cpp.
#include <stddef.h>
#include <string_view>

namespace caml_replacement {

enum class Site {
    Setter,  // CCUIButtonModuleView / CCUIRoundButton: exact-name map route
    Slider,  // CCUIBaseSliderView: verified containsString: route
};

struct Mapping {
    const char *packageName;     // incoming packageURL filename stem
    const char *bundleDirectory; // theme directory under <theme>/Assets/
};

// Bundle directories with a themed "<packageName>.ca" package. "Mute" exists
// in both MuteModule.bundle and SpringBoard.framework themes; the original
// dictionary could map it to only one directory and MuteModule.bundle is the
// module-identity match (residual ambiguity recorded in the handoff).
static constexpr Mapping kPackageBundles[] = {
    {"AirPlayControlAudioDark", "MediaControls.framework"},
    {"AirPlayControlAudioLight", "MediaControls.framework"},
    {"Bluetooth", "ConnectivityModule.bundle"},
    {"Brightness", "DisplayModule.bundle"},
    {"ForwardBackward", "MediaControls.framework"},
    {"HAE_1_x_1", "HearingAidsModule.bundle"},
    {"LowPower", "LowPowerModule.bundle"},
    {"MPAVScreenMirroring", "AirPlayMirroringModule.bundle"},
    {"Mirroring", "MediaControls.framework"},
    {"MirroringNonAnimated", "MediaControls.framework"},
    {"Mute", "MuteModule.bundle"},
    {"OrientationLock", "OrientationLockModule.bundle"},
    {"PlayPauseStop", "MediaControls.framework"},
    {"Ringer-Leading-D73", "SpringBoard.framework"},
    {"Ringer-Minimal-D73", "SpringBoard.framework"},
    {"Shazam", "ShazamModule.bundle"},
    {"StyleMode", "AppearanceModule.bundle"},
    {"Volume", "MediaControls.framework"},
    {"dnd_cg_02", "FocusUI.framework"},
    {"replaykit", "ReplayKitModule.bundle"},
    {"replaykit-v2", "ReplayKitModule.bundle"},
    {"timer", "TimerModule.bundle"},
    {"WiFi", "ConnectivityModule.bundle"},
};
static constexpr size_t kPackageBundleCount = sizeof(kPackageBundles) / sizeof(kPackageBundles[0]);

inline bool Contains(std::string_view value, std::string_view part) {
    return !part.empty() && value.find(part) != std::string_view::npos;
}

// Returns the theme bundle directory to route through, or nullptr for
// fail-open pass-through of the original description. themeType is the raw
// kThemeType preference (0 = Plampy, 1 = Pulsar).
inline const char *BundleDirectoryForPackage(std::string_view name, Site site, int themeType) {
    if (name.empty()) return nullptr;
    if (site == Site::Slider) {
        // Original slider variant (sub_93cc): containsString: dispatch only.
        if (Contains(name, "Brightness")) return "DisplayModule.bundle";
        if (Contains(name, "Volume")) return "MediaControls.framework";
        return nullptr;
    }
    for (const Mapping &entry : kPackageBundles) {
        if (name == entry.packageName) {
            // Verified special case (sub_8c98): timer under the Pulsar theme
            // keeps the stock description.
            if (name == "timer" && themeType == 1) return nullptr;
            return entry.bundleDirectory;
        }
    }
    return nullptr; // dictionary-miss semantics: fail open
}

// ---- Live preference reconciliation policy (SP1) ----
//
// The three verified 21D50 setter seams (ABI map §2 rows 1-3) each carry a
// stable integer identity across the shim/ARC boundary. The routing split
// (exact-name map vs slider containsString: route) is derived, never assumed.
enum class Seam : int {
    ButtonPackage = 0, // CCUIButtonModuleView setGlyphPackageDescription:
    RoundPackage = 1,  // CCUIRoundButton setGlyphPackageDescription:
    SliderPackage = 2, // CCUIBaseSliderView setGlyphPackageDescription:
};

inline Site RoutingSiteFor(Seam seam) {
    return seam == Seam::SliderPackage ? Site::Slider : Site::Setter;
}

// What the verified read-back (glyphPackageDescription) shows in a consumer
// relative to the recorded original/applied pair:
//   OwnedReplacement — our applied replacement is still installed (ownership
//                      intact; restoration of the original is safe).
//   StockUnchanged   — the preserved original stock description is installed
//                      (stock untouched; nothing to restore).
//   StockChanged     — a newer stock description we never saw through the
//                      intercepted seams is installed. It is adopted as the
//                      recovery original; restoration must never overwrite it.
//   NoDescription    — the consumer currently has no package description;
//                      nothing is owned or restored (fail open, untouched).
enum class InstallObservation {
    OwnedReplacement,
    StockUnchanged,
    StockChanged,
    NoDescription,
};

inline InstallObservation ClassifyInstall(bool installedPresent, bool installedIsApplied,
                                          bool installedIsOriginal) {
    if (!installedPresent) return InstallObservation::NoDescription;
    if (installedIsApplied) return InstallObservation::OwnedReplacement;
    if (installedIsOriginal) return InstallObservation::StockUnchanged;
    return InstallObservation::StockChanged;
}

enum class ReconcileAction {
    KeepInstalled,    // leave the installed description untouched
    ApplyReplacement, // install a freshly constructed owned replacement
    RestoreStock,     // install the preserved original stock description
};

struct ReconcileFacts {
    bool enabled;                // functional preference gate
    bool replacementAvailable;   // factory produced a replacement for (stem, theme)
    InstallObservation observation;
    bool ownedThemeSatisfies;    // the recorded applied theme matches the current theme
};

// The complete reconcile decision table: disabled-start and re-enable,
// Plampy<->Pulsar theme changes, disable/re-enable, missing or unsupported
// resources, newer stock assignments (never overwritten), and consumers with
// nothing installed all resolve here. Deterministic and side-effect free.
inline ReconcileAction DecideReconcile(const ReconcileFacts &facts) {
    if (facts.observation == InstallObservation::NoDescription) return ReconcileAction::KeepInstalled;
    const bool owned = facts.observation == InstallObservation::OwnedReplacement;
    if (facts.enabled && facts.replacementAvailable) {
        return (owned && facts.ownedThemeSatisfies) ? ReconcileAction::KeepInstalled
                                                   : ReconcileAction::ApplyReplacement;
    }
    return owned ? ReconcileAction::RestoreStock : ReconcileAction::KeepInstalled;
}

// ---- owned-description recovery transitions (SP1-R1) ----
//
// An intercepted setter input is not necessarily stock: a caller may
// re-assign a description we previously installed (ABI map §4 explicitly
// describes valid same-object setter assignments). Recording every input as
// "stock" loses the real stock recovery object, so each input is classified
// against the recorded owned/applied state BEFORE construction and recording:
//   - an owned replacement is never a stock recovery candidate; the preserved
//     real-stock original survives the re-assignment (and survives a failed
//     reconstruction), so disable/restore can never reinstall a themed
//     description as "stock";
//   - only a genuinely newer stock description is adopted as the recovery
//     original (newest stock wins);
//   - ownership is dropped only when a genuine stock description actually
//     replaces our replacement at the setter.
//
// Descriptions are opaque handles. The adapter (src/CAMLReplacement.xm)
// supplies identity/equality and ownership predicates (its owned-marker
// association plus SameDescription), and tests inject fakes and assert handle
// identity, so original/identity preservation is exercised against the exact
// production transitions below. Object lifetimes themselves (associated-object
// teardown, weak-registry zeroing) are Foundation runtime behavior and are
// never claimed by these host-testable transitions.
using DescriptionHandle = const void *;
using HandleEqual = bool (*)(DescriptionHandle, DescriptionHandle);
using HandleOwned = bool (*)(DescriptionHandle); // "this description is ours"

struct RecoveryState {
    DescriptionHandle original; // newest genuine stock description (never ours)
    DescriptionHandle applied;  // our owned replacement currently recorded
    int appliedTheme;           // theme `applied` was built for; -1 when unknown
};

inline RecoveryState NoRecoveryState() { return RecoveryState{nullptr, nullptr, -1}; }

enum class IncomingKind {
    OwnedReplacement, // the input is a replacement we constructed (never stock)
    NewStock,         // a genuine stock description (the newest one wins)
};

// Classify an intercepted setter input against the recorded state. The
// ownership predicate covers replacements whose record is already gone (for
// example a stale reference re-assigned after restoration): ours is never
// "genuinely newer stock".
inline IncomingKind ClassifyIncoming(const RecoveryState &prior, bool hasPrior,
                                     DescriptionHandle incoming, HandleEqual equal,
                                     HandleOwned isOwned) {
    if (isOwned(incoming)) return IncomingKind::OwnedReplacement;
    if (hasPrior && prior.applied && equal(incoming, prior.applied))
        return IncomingKind::OwnedReplacement;
    return IncomingKind::NewStock;
}

// Construction-side decision (runs inside the factory before any build).
struct ConstructionPlan {
    bool keepOwned;           // input is our still-valid replacement: build nothing
    DescriptionHandle source; // the real stock description to construct from
};

inline ConstructionPlan PlanConstruction(const RecoveryState &prior, bool hasPrior,
                                         DescriptionHandle incoming, int currentTheme,
                                         HandleEqual equal, HandleOwned isOwned) {
    if (ClassifyIncoming(prior, hasPrior, incoming, equal, isOwned) == IncomingKind::NewStock)
        return ConstructionPlan{false, incoming};
    // Owned input: rebuild from the preserved real stock — never from the owned
    // replacement itself — and keep the recorded replacement as-is while it is
    // the current applied object and already built for the current theme.
    DescriptionHandle stock = (hasPrior && prior.original) ? prior.original : incoming;
    bool keep = hasPrior && prior.applied && equal(incoming, prior.applied) &&
                prior.appliedTheme == currentTheme;
    return ConstructionPlan{keep, stock};
}

// Record-side transition (runs after the original setter invocation).
// `installed` is what the original setter received: the freshly constructed
// replacement when `installedOwned`, otherwise the input description itself.
struct InstallInput {
    RecoveryState prior;
    bool hasPrior;
    DescriptionHandle incoming;
    DescriptionHandle installed;
    bool installedOwned;
    int theme; // current theme (the theme `installedOwned` was built for)
    int seam;
};

inline RecoveryState RecordInstall(const InstallInput &input, HandleEqual equal,
                                   HandleOwned isOwned) {
    const IncomingKind kind =
        ClassifyIncoming(input.prior, input.hasPrior, input.incoming, equal, isOwned);
    // Only genuine stock can become the recovery original; an owned input
    // preserves the previously recorded original (which may be unknown — never
    // the themed input itself).
    DescriptionHandle original = kind == IncomingKind::NewStock
                                     ? input.incoming
                                     : (input.hasPrior ? input.prior.original : nullptr);
    if (input.installedOwned) {
        // A fresh replacement was constructed and installed; it owns the
        // consumer now, under the current theme.
        return RecoveryState{original, input.installed, input.theme};
    }
    if (kind == IncomingKind::OwnedReplacement) {
        // Reconstruction missed (disabled, resource miss, keep-owned) and the
        // owned replacement passed through: ownership survives the miss. Only
        // an unrecognized build theme is recorded conservatively as -1 so a
        // later reconcile rebuilds instead of trusting a stale theme claim.
        DescriptionHandle applied = input.installed;
        int appliedTheme = (input.hasPrior && input.prior.applied &&
                            equal(input.installed, input.prior.applied))
                               ? input.prior.appliedTheme
                               : -1;
        return RecoveryState{original, applied, appliedTheme};
    }
    // Genuine stock pass-through: nothing of ours is installed any more.
    return RecoveryState{original, nullptr, -1};
}

// Reconcile-side transition, phase 1: classify the verified read-back and
// adopt genuinely newer stock before any construction is attempted.
struct ReconcileObservation {
    InstallObservation kind;
    bool clear;                           // NoDescription: drop the record and stop
    RecoveryState base;                   // state after newer-stock adoption
    DescriptionHandle constructionSource; // real stock to rebuild from; null: none
};

inline ReconcileObservation ObserveReconcile(const RecoveryState &prior, bool hasPrior,
                                             DescriptionHandle installed,
                                             bool installedPresent, HandleEqual equal) {
    const bool installedIsApplied = hasPrior && prior.applied && equal(installed, prior.applied);
    const bool installedIsOriginal =
        hasPrior && prior.original && equal(installed, prior.original);
    const InstallObservation kind =
        ClassifyInstall(installedPresent, installedIsApplied, installedIsOriginal);
    if (kind == InstallObservation::NoDescription)
        return ReconcileObservation{kind, true, NoRecoveryState(), nullptr};
    if (kind == InstallObservation::StockChanged) {
        // A genuinely newer stock description (assigned outside the intercepted
        // seams, or the first observation of this consumer) is installed: adopt
        // it as the recovery original and drop ownership so restoration can
        // never overwrite it.
        return ReconcileObservation{kind, false, RecoveryState{installed, nullptr, -1},
                                   installed};
    }
    // OwnedReplacement or StockUnchanged: the preserved original stands, and
    // any rebuild constructs from the real stock, never from our replacement.
    return ReconcileObservation{kind, false, prior, prior.original};
}

// Reconcile-side transition, phase 2: the decision plus the exact state to
// persist and the exact description (if any) for the original setter.
struct ReconcilePlan {
    ReconcileAction action;
    bool perform;             // invoke the original setter with `invoke`
    DescriptionHandle invoke; // the description to hand to the original setter
    int seam;
    bool clear;         // drop the record after the action
    RecoveryState next; // the state to persist when not cleared
};

inline ReconcilePlan PlanReconcileAction(const RecoveryState &base, InstallObservation observation,
                                         DescriptionHandle installed, bool enabled,
                                         DescriptionHandle desired, int theme, int seam,
                                         HandleEqual equal) {
    if (observation == InstallObservation::NoDescription) {
        // Nothing installed: nothing to own or recover. Never invoke a setter.
        return ReconcilePlan{ReconcileAction::KeepInstalled, false, nullptr, seam, true,
                             NoRecoveryState()};
    }
    const bool installedIsApplied = base.applied && equal(installed, base.applied);
    const bool ownedThemeSatisfies = installedIsApplied && base.appliedTheme == theme;
    const ReconcileAction action = DecideReconcile(
        ReconcileFacts{enabled, desired != nullptr, observation, ownedThemeSatisfies});
    switch (action) {
        case ReconcileAction::ApplyReplacement:
            if (!desired) break; // defensive: never "install nothing"
            return ReconcilePlan{action, true, desired, seam, false,
                                 RecoveryState{base.original, desired, theme}};
        case ReconcileAction::RestoreStock:
            // Only reachable while our applied replacement is provably
            // installed. Without a preserved real stock object (only possible
            // for an owned input recorded before it ever had one) fail open and
            // leave the installed description untouched.
            if (!base.original) break;
            return ReconcilePlan{action, true, base.original, seam, true, NoRecoveryState()};
        case ReconcileAction::KeepInstalled:
            break;
    }
    // KeepInstalled, or a guarded fail-open above: preserve the installed
    // description and keep ownership only while it is still ours.
    return ReconcilePlan{ReconcileAction::KeepInstalled, false, nullptr, seam, false,
                         RecoveryState{base.original, installedIsApplied ? base.applied : nullptr,
                                       installedIsApplied ? base.appliedTheme : -1}};
}

} // namespace caml_replacement
#endif

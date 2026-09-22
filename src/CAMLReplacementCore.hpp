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

} // namespace caml_replacement
#endif

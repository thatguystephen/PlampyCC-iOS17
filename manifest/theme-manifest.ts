// PlampyCC checked-in theme manifest (M0).
//
// Typed data only — no executable discovery logic. This file is the single
// canonical Module Identity / Capability vocabulary for iPhone15,2 / iOS 17.3 /
// build 21D50. It is copied 1:1 from the immutable canonical seed
// (manifest/21d50-canonical-manifest-seed.json, SHA-256
// 63252e96ade77361484a75eade500bc7a653965ead644f11eaffe02cc2a7ef99, derived from
// accepted asset-map source SHA-256
// d1d990e14cbbb683cfd5a42a924ec1839303e1cc4499bf0c976e89c9aabd9919).
//
// Preservation contract (enforced by tests/theme-manifest-parity.ts):
// every seed record, disposition, name (stockAliases), asset path
// (stockAssets), and stock default (safeDefault) is preserved verbatim in
// `seedDisposition` / `stockAliases` / `stockAssets` / `safeDefault`.
//
// EvidenceDisposition mapping rule (deterministic, total; seed fields kept on
// each record so the mapping is machine-checkable):
//   verified_asset_candidate                                  -> eligible
//   unknown_renderer_stock                                    -> stock-only-unknown
//   missing_asset_stock + module renderer "inferred"           -> stock-only-inferred
//   missing_asset_stock                                       -> stock-only-missing
//   unresolved_catalog_stock + capability evidence "static_png" -> stock-only-static
//   unresolved_catalog_stock + capability evidence "unknown"    -> stock-only-opaque
//
// Catalog eligibility is independent of lifecycle activation: a capability may
// be `eligible` with `lifecycleEvidence: null`. It may enter an artifact's
// activation set only once its direct 21D50 lifecycle evidence record is
// complete. Exactly one stage is selected per artifact; M0 selects Q0 with an
// empty activation set.

export type Target = {
  readonly productType: "iPhone15,2";
  readonly productVersion: "17.3";
  readonly build: "21D50";
};

export type EvidenceDisposition =
  | "eligible"
  | "stock-only-opaque"
  | "stock-only-static"
  | "stock-only-inferred"
  | "stock-only-unknown"
  | "stock-only-missing";

export type SeedDisposition =
  | "verified_asset_candidate"
  | "missing_asset_stock"
  | "unknown_renderer_stock"
  | "unresolved_catalog_stock";

export type SeedEvidenceType = "animated_caml" | "static_png" | "unknown";

export type RendererFamily = "caml-package-setter";

export type StageName = "Q0" | "A1" | "A2" | "A3" | "R1";

export type HostForm = "button-host" | "slider-host" | "expansion-host" | "unknown-host";

export type LifecycleEvidenceId = string;

export type ModuleId =
  | "AccessibilityGuidedAccessControlCenterModule"
  | "AccessibilityShorcutsModule"
  | "AccessibilitySoundDetectionControlCenterModule"
  | "AccessibilityTextSizeModule"
  | "AirPlayMirroringModule"
  | "AlarmModule"
  | "AppearanceModule"
  | "CalculatorModule"
  | "CameraModule"
  | "ConnectivityModule"
  | "DisplayModule"
  | "FlashlightModule"
  | "FocusUI"
  | "HearingAidsModule"
  | "LowPowerModule"
  | "MagnifierModule"
  | "MediaControls"
  | "MuteModule"
  | "NFCControlCenterModule"
  | "OrientationLockModule"
  | "PerformanceTraceModule"
  | "QRCodeModule"
  | "ReplayKitModule"
  | "ShazamModule"
  | "SpringBoard_Ringer"
  | "StopwatchModule"
  | "TimerModule"
  | "TVRemoteModule"
  | "VoiceMemosModule"
  | "WalletModule";

export type CapabilityId =
  | "accessibility-guided-access"
  | "accessibility-shortcuts"
  | "accessibility-sound-detection"
  | "accessibility-text-size"
  | "airplay-mirroring"
  | "alarm"
  | "appearance"
  | "calculator"
  | "camera"
  | "connectivity-caml"
  | "connectivity-glyphs"
  | "display-brightness"
  | "display-catalog"
  | "flashlight"
  | "focus"
  | "hearing-aids"
  | "low-power"
  | "magnifier"
  | "media-controls-volume"
  | "mute"
  | "nfc"
  | "orientation-lock"
  | "performance-trace"
  | "qr-code"
  | "replaykit"
  | "shazam"
  | "springboard-ringer"
  | "stopwatch"
  | "timer"
  | "tv-remote"
  | "voice-memos"
  | "wallet";

export type PlampyPackageRoute = {
  readonly packageName: string;
  readonly bundleDir: string;
  // Repo-relative staged Plampy asset that must exist at generation time.
  readonly requiredAsset: string;
};

export type PlampyRecipe = {
  readonly packages: readonly PlampyPackageRoute[];
};

export type AliasDisambiguation = {
  readonly alias: string;
  readonly resolution: string;
  readonly rationale: string;
};

export type DeviceTestVector = {
  readonly visibleStates: readonly string[];
  readonly presentations: readonly ("compact" | "expanded")[];
};

export type CapabilityRecord = {
  readonly id: CapabilityId;
  readonly module: ModuleId;
  readonly localIndex: number;
  readonly disposition: EvidenceDisposition;
  readonly seedDisposition: SeedDisposition;
  readonly seedEvidenceType: SeedEvidenceType;
  readonly rendererFamily: RendererFamily | null;
  readonly hostForm: HostForm;
  readonly stockAliases: readonly string[];
  readonly stockAssets: readonly string[];
  readonly aliasDisambiguation?: AliasDisambiguation;
  readonly plampyRecipe: PlampyRecipe | null;
  readonly lifecycleEvidence: LifecycleEvidenceId | null;
  readonly deviceVector: DeviceTestVector;
};

export type ModuleRecord = {
  readonly id: ModuleId;
  readonly safeDefault: "stock";
  readonly seedRendererEvidenceStatus: "verified" | "inferred" | "unknown";
  readonly capabilities: readonly CapabilityId[];
};

// Direct 21D50 lifecycle evidence record. Not parsed by SpringBoard; inputs to
// generation and review only. A record is complete only when every field names
// a direct 21D50 fact (see tools/theme-catalog/validate.ts).
export type LifecycleEvidenceRecord = {
  readonly id: LifecycleEvidenceId;
  readonly module: ModuleId;
  readonly capability: CapabilityId;
  readonly ownerClass: string;
  readonly hostClass: string;
  readonly bindSelector: string;
  readonly closeSignal: string;
  readonly detachSignal: string;
  readonly reuseSignal: string;
  readonly selectorEncodings: Readonly<Record<string, string>>;
  readonly callSiteSources: readonly string[];
  readonly epochInvalidation: string;
  readonly producerTagPath: string;
  readonly stockCapturePath: string;
  readonly newerStockAdoptionPath: string;
  readonly restorationPath: string;
  readonly teardownPath: string;
  readonly missingFactCondition: string;
};

export type StageActivation = {
  readonly name: StageName;
  readonly activeCapabilities: readonly CapabilityId[];
};

// Typed adapter declaration for a Renderer Family. Generation fails when a
// capability names a Renderer Family with no typed adapter entry here.
export type RendererFamilyAdapter = {
  readonly family: RendererFamily;
  readonly adapter: string;
  readonly seams: readonly {
    readonly name: string;
    readonly ownerClass: string;
    readonly selector: string;
    readonly encoding: string;
    readonly predecessorType: string;
  }[];
};

export const rendererFamilyAdapters: readonly RendererFamilyAdapter[] = [
  {
    family: "caml-package-setter",
    adapter: "CAMLAdapter",
    seams: [
      {
        name: "button-package",
        ownerClass: "CCUIButtonModuleView",
        selector: "setGlyphPackageDescription:",
        encoding: "v24@0:8@16",
        predecessorType: "void (*)(id, SEL, id)",
      },
      {
        name: "round-package",
        ownerClass: "CCUIRoundButton",
        selector: "setGlyphPackageDescription:",
        encoding: "v24@0:8@16",
        predecessorType: "void (*)(id, SEL, id)",
      },
      {
        name: "slider-package",
        ownerClass: "CCUIBaseSliderView",
        selector: "setGlyphPackageDescription:",
        encoding: "v24@0:8@16",
        predecessorType: "void (*)(id, SEL, id)",
      },
    ],
  },
];

export const target: Target = {
  productType: "iPhone15,2",
  productVersion: "17.3",
  build: "21D50",
};

export const seed = {
  file: "manifest/21d50-canonical-manifest-seed.json",
  sha256: "63252e96ade77361484a75eade500bc7a653965ead644f11eaffe02cc2a7ef99",
  sourceSha256: "d1d990e14cbbb683cfd5a42a924ec1839303e1cc4499bf0c976e89c9aabd9919",
} as const;

const plampyAsset = (bundleDir: string, packageName: string): string =>
  `layout/Library/Application Support/PlampyCC/Plampy/Assets/${bundleDir}/${packageName}.ca/main.caml`;

export const modules: readonly ModuleRecord[] = [
  {
    id: "AccessibilityGuidedAccessControlCenterModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["accessibility-guided-access"],
  },
  {
    id: "AccessibilityShorcutsModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["accessibility-shortcuts"],
  },
  {
    id: "AccessibilitySoundDetectionControlCenterModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["accessibility-sound-detection"],
  },
  {
    id: "AccessibilityTextSizeModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["accessibility-text-size"],
  },
  {
    id: "AirPlayMirroringModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["airplay-mirroring"],
  },
  {
    id: "AlarmModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["alarm"],
  },
  {
    id: "AppearanceModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["appearance"],
  },
  {
    id: "CalculatorModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["calculator"],
  },
  {
    id: "CameraModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["camera"],
  },
  {
    id: "ConnectivityModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["connectivity-caml", "connectivity-glyphs"],
  },
  {
    id: "DisplayModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["display-brightness", "display-catalog"],
  },
  {
    id: "FlashlightModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["flashlight"],
  },
  {
    id: "FocusUI",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["focus"],
  },
  {
    id: "HearingAidsModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "inferred",
    capabilities: ["hearing-aids"],
  },
  {
    id: "LowPowerModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["low-power"],
  },
  {
    id: "MagnifierModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["magnifier"],
  },
  {
    id: "MediaControls",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["media-controls-volume"],
  },
  {
    id: "MuteModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["mute"],
  },
  {
    id: "NFCControlCenterModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["nfc"],
  },
  {
    id: "OrientationLockModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["orientation-lock"],
  },
  {
    id: "PerformanceTraceModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["performance-trace"],
  },
  {
    id: "QRCodeModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["qr-code"],
  },
  {
    id: "ReplayKitModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["replaykit"],
  },
  {
    id: "ShazamModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["shazam"],
  },
  {
    id: "SpringBoard_Ringer",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["springboard-ringer"],
  },
  {
    id: "StopwatchModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["stopwatch"],
  },
  {
    id: "TimerModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["timer"],
  },
  {
    id: "TVRemoteModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["tv-remote"],
  },
  {
    id: "VoiceMemosModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["voice-memos"],
  },
  {
    id: "WalletModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "unknown",
    capabilities: ["wallet"],
  },
];

export const capabilities: readonly CapabilityRecord[] = [
  {
    id: "accessibility-guided-access",
    module: "AccessibilityGuidedAccessControlCenterModule",
    localIndex: 0,
    disposition: "stock-only-missing",
    seedDisposition: "missing_asset_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "unknown-host",
    stockAliases: [],
    stockAssets: [],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "accessibility-shortcuts",
    module: "AccessibilityShorcutsModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "expansion-host",
    stockAliases: ["AccessibilityIcon"],
    stockAssets: ["AccessibilityShorcutsModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["list"], presentations: ["compact", "expanded"] },
  },
  {
    id: "accessibility-sound-detection",
    module: "AccessibilitySoundDetectionControlCenterModule",
    localIndex: 0,
    disposition: "stock-only-missing",
    seedDisposition: "missing_asset_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "unknown-host",
    stockAliases: [],
    stockAssets: [],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "accessibility-text-size",
    module: "AccessibilityTextSizeModule",
    localIndex: 0,
    disposition: "stock-only-missing",
    seedDisposition: "missing_asset_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "slider-host",
    stockAliases: [],
    stockAssets: [],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact", "expanded"] },
  },
  {
    id: "airplay-mirroring",
    module: "AirPlayMirroringModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["MPAVScreenMirroring"],
    stockAssets: ["AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "MPAVScreenMirroring",
          bundleDir: "AirPlayMirroringModule.bundle",
          requiredAsset: plampyAsset("AirPlayMirroringModule.bundle", "MPAVScreenMirroring"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["off", "on"], presentations: ["compact"] },
  },
  {
    id: "alarm",
    module: "AlarmModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: [],
    stockAssets: ["AlarmModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "appearance",
    module: "AppearanceModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["StyleMode"],
    stockAssets: ["AppearanceModule.bundle/StyleMode.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "StyleMode",
          bundleDir: "AppearanceModule.bundle",
          requiredAsset: plampyAsset("AppearanceModule.bundle", "StyleMode"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["light", "dark"], presentations: ["compact", "expanded"] },
  },
  {
    id: "calculator",
    module: "CalculatorModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["Calculator"],
    stockAssets: ["CalculatorModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "camera",
    module: "CameraModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["Camera"],
    stockAssets: ["CameraModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "connectivity-caml",
    module: "ConnectivityModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "expansion-host",
    stockAliases: ["Bluetooth", "WiFi"],
    stockAssets: [
      "ConnectivityModule.bundle/Bluetooth.ca",
      "ConnectivityModule.bundle/WiFi.ca",
    ],
    plampyRecipe: {
      packages: [
        {
          packageName: "Bluetooth",
          bundleDir: "ConnectivityModule.bundle",
          requiredAsset: plampyAsset("ConnectivityModule.bundle", "Bluetooth"),
        },
        {
          packageName: "WiFi",
          bundleDir: "ConnectivityModule.bundle",
          requiredAsset: plampyAsset("ConnectivityModule.bundle", "WiFi"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["inactive", "active"], presentations: ["compact", "expanded"] },
  },
  {
    id: "connectivity-glyphs",
    module: "ConnectivityModule",
    localIndex: 1,
    disposition: "stock-only-static",
    seedDisposition: "unresolved_catalog_stock",
    seedEvidenceType: "static_png",
    rendererFamily: null,
    hostForm: "expansion-host",
    stockAliases: ["AirplaneGlyph", "CellularDataGlyph", "AirDropGlyph", "HotspotGlyph"],
    stockAssets: ["ConnectivityModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["visible"], presentations: ["compact", "expanded"] },
  },
  {
    id: "display-brightness",
    module: "DisplayModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "slider-host",
    stockAliases: ["Brightness"],
    stockAssets: ["DisplayModule.bundle/Brightness.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "Brightness",
          bundleDir: "DisplayModule.bundle",
          requiredAsset: plampyAsset("DisplayModule.bundle", "Brightness"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["low", "high"], presentations: ["compact", "expanded"] },
  },
  {
    id: "display-catalog",
    module: "DisplayModule",
    localIndex: 1,
    disposition: "stock-only-opaque",
    seedDisposition: "unresolved_catalog_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "expansion-host",
    stockAliases: [],
    stockAssets: ["DisplayModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["visible"], presentations: ["compact", "expanded"] },
  },
  {
    id: "flashlight",
    module: "FlashlightModule",
    localIndex: 0,
    disposition: "stock-only-static",
    seedDisposition: "unresolved_catalog_stock",
    seedEvidenceType: "static_png",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["FlashlightOn", "FlashlightOff"],
    stockAssets: ["FlashlightModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["off", "on"], presentations: ["compact"] },
  },
  {
    id: "focus",
    module: "FocusUI",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["dnd_cg_02"],
    stockAssets: ["FocusUI.framework/dnd_cg_02.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "dnd_cg_02",
          bundleDir: "FocusUI.framework",
          requiredAsset: plampyAsset("FocusUI.framework", "dnd_cg_02"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["off", "on"], presentations: ["compact", "expanded"] },
  },
  {
    id: "hearing-aids",
    module: "HearingAidsModule",
    localIndex: 0,
    disposition: "stock-only-inferred",
    seedDisposition: "missing_asset_stock",
    seedEvidenceType: "animated_caml",
    rendererFamily: null,
    hostForm: "unknown-host",
    stockAliases: ["HAE_1_x_1"],
    stockAssets: ["HearingAidsModule.bundle/HAE_1_x_1.ca"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "low-power",
    module: "LowPowerModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["LowPower", "LowPower-light", "LowPower_IC", "LowPower_IC-light"],
    stockAssets: ["LowPowerModule.bundle/LowPower.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "LowPower",
          bundleDir: "LowPowerModule.bundle",
          requiredAsset: plampyAsset("LowPowerModule.bundle", "LowPower"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["off", "on"], presentations: ["compact"] },
  },
  {
    id: "magnifier",
    module: "MagnifierModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["Magnifier"],
    stockAssets: ["MagnifierModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "media-controls-volume",
    module: "MediaControls",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "slider-host",
    stockAliases: [
      "Volume",
      "PlayPauseStop",
      "ForwardBackward",
      "Mirroring",
      "MirroringNonAnimated",
      "AirPlayControlAudioDark",
      "AirPlayControlAudioLight",
    ],
    stockAssets: [
      "MediaControls.framework/Volume.ca",
      "MediaControls.framework/PlayPauseStop.ca",
      "MediaControls.framework/ForwardBackward.ca",
      "MediaControls.framework/Mirroring.ca",
      "MediaControls.framework/MirroringNonAnimated.ca",
      "MediaControls.framework/AirPlayControlAudioDark.ca",
      "MediaControls.framework/AirPlayControlAudioLight.ca",
    ],
    plampyRecipe: {
      packages: [
        {
          packageName: "Volume",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "Volume"),
        },
        {
          packageName: "PlayPauseStop",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "PlayPauseStop"),
        },
        {
          packageName: "ForwardBackward",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "ForwardBackward"),
        },
        {
          packageName: "Mirroring",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "Mirroring"),
        },
        {
          packageName: "MirroringNonAnimated",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "MirroringNonAnimated"),
        },
        {
          packageName: "AirPlayControlAudioDark",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "AirPlayControlAudioDark"),
        },
        {
          packageName: "AirPlayControlAudioLight",
          bundleDir: "MediaControls.framework",
          requiredAsset: plampyAsset("MediaControls.framework", "AirPlayControlAudioLight"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["low", "high"], presentations: ["compact", "expanded"] },
  },
  {
    id: "mute",
    module: "MuteModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["Mute"],
    stockAssets: ["MuteModule.bundle/Mute.ca"],
    aliasDisambiguation: {
      alias: "Mute",
      resolution: "MuteModule.bundle",
      rationale:
        "package stem Mute exists under both MuteModule.bundle and SpringBoard.framework; the module-identity match selects MuteModule.bundle (see CAMLReplacementCore.hpp kPackageBundles)",
    },
    plampyRecipe: {
      packages: [
        {
          packageName: "Mute",
          bundleDir: "MuteModule.bundle",
          requiredAsset: plampyAsset("MuteModule.bundle", "Mute"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["on", "off"], presentations: ["compact"] },
  },
  {
    id: "nfc",
    module: "NFCControlCenterModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: [],
    stockAssets: ["NFCControlCenterModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "orientation-lock",
    module: "OrientationLockModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["OrientationLock"],
    stockAssets: ["OrientationLockModule.bundle/OrientationLock.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "OrientationLock",
          bundleDir: "OrientationLockModule.bundle",
          requiredAsset: plampyAsset("OrientationLockModule.bundle", "OrientationLock"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["unlocked", "locked"], presentations: ["compact"] },
  },
  {
    id: "performance-trace",
    module: "PerformanceTraceModule",
    localIndex: 0,
    disposition: "stock-only-missing",
    seedDisposition: "missing_asset_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "unknown-host",
    stockAliases: [],
    stockAssets: [],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "qr-code",
    module: "QRCodeModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["QRCode"],
    stockAssets: ["QRCodeModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "replaykit",
    module: "ReplayKitModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["replaykit", "replaykit-v2"],
    stockAssets: [
      "ReplayKitModule.bundle/replaykit.ca",
      "ReplayKitModule.bundle/replaykit-v2.ca",
    ],
    plampyRecipe: {
      packages: [
        {
          packageName: "replaykit",
          bundleDir: "ReplayKitModule.bundle",
          requiredAsset: plampyAsset("ReplayKitModule.bundle", "replaykit"),
        },
        {
          packageName: "replaykit-v2",
          bundleDir: "ReplayKitModule.bundle",
          requiredAsset: plampyAsset("ReplayKitModule.bundle", "replaykit-v2"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["idle", "recording"], presentations: ["compact"] },
  },
  {
    id: "shazam",
    module: "ShazamModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["Shazam"],
    stockAssets: ["ShazamModule.bundle/Shazam.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "Shazam",
          bundleDir: "ShazamModule.bundle",
          requiredAsset: plampyAsset("ShazamModule.bundle", "Shazam"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["idle", "listening"], presentations: ["compact"] },
  },
  {
    id: "springboard-ringer",
    module: "SpringBoard_Ringer",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["Ringer-Leading-D73", "Ringer-Minimal-D73"],
    stockAssets: [
      "SpringBoard.framework/Ringer-Leading-D73.ca",
      "SpringBoard.framework/Ringer-Minimal-D73.ca",
    ],
    plampyRecipe: {
      packages: [
        {
          packageName: "Ringer-Leading-D73",
          bundleDir: "SpringBoard.framework",
          requiredAsset: plampyAsset("SpringBoard.framework", "Ringer-Leading-D73"),
        },
        {
          packageName: "Ringer-Minimal-D73",
          bundleDir: "SpringBoard.framework",
          requiredAsset: plampyAsset("SpringBoard.framework", "Ringer-Minimal-D73"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["on", "off"], presentations: ["compact"] },
  },
  {
    id: "stopwatch",
    module: "StopwatchModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: [],
    stockAssets: ["StopwatchModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["idle", "running"], presentations: ["compact"] },
  },
  {
    id: "timer",
    module: "TimerModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["timer"],
    stockAssets: ["TimerModule.bundle/timer.ca"],
    plampyRecipe: {
      packages: [
        {
          packageName: "timer",
          bundleDir: "TimerModule.bundle",
          requiredAsset: plampyAsset("TimerModule.bundle", "timer"),
        },
      ],
    },
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["idle", "running"], presentations: ["compact"] },
  },
  {
    id: "tv-remote",
    module: "TVRemoteModule",
    localIndex: 0,
    disposition: "stock-only-static",
    seedDisposition: "unresolved_catalog_stock",
    seedEvidenceType: "static_png",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["ModuleIcon"],
    stockAssets: ["TVRemoteModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "voice-memos",
    module: "VoiceMemosModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: ["VoiceMemos"],
    stockAssets: ["VoiceMemosModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
  {
    id: "wallet",
    module: "WalletModule",
    localIndex: 0,
    disposition: "stock-only-unknown",
    seedDisposition: "unknown_renderer_stock",
    seedEvidenceType: "unknown",
    rendererFamily: null,
    hostForm: "button-host",
    stockAliases: [],
    stockAssets: ["WalletModule.bundle/Assets.car"],
    plampyRecipe: null,
    lifecycleEvidence: null,
    deviceVector: { visibleStates: ["default"], presentations: ["compact"] },
  },
];

// Direct 21D50 lifecycle evidence records. M0 owns none: no capability may be
// activated yet. Records are added by later milestones as evidence closes.
export const lifecycleEvidenceRecords: Readonly<Record<LifecycleEvidenceId, LifecycleEvidenceRecord>> = {};

// Exactly one stage is selected per artifact. M0 selects Q0 with an empty
// activation set; every capability stays stock.
export const selectedStage: StageActivation = {
  name: "Q0",
  activeCapabilities: [],
};

export type ThemeManifest = {
  readonly schema: "plampycc-theme-manifest/v1";
  readonly target: Target;
  readonly seed: typeof seed;
  readonly modules: readonly ModuleRecord[];
  readonly capabilities: readonly CapabilityRecord[];
  readonly rendererFamilyAdapters: readonly RendererFamilyAdapter[];
  readonly lifecycleEvidenceRecords: Readonly<Record<LifecycleEvidenceId, LifecycleEvidenceRecord>>;
  readonly selectedStage: StageActivation;
};

export const manifest: ThemeManifest = {
  schema: "plampycc-theme-manifest/v1",
  target,
  seed,
  modules,
  capabilities,
  rendererFamilyAdapters,
  lifecycleEvidenceRecords,
  selectedStage,
};

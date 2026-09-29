// Theme catalog validation (M0).
//
// One deterministic operation: validate the checked-in manifest against the
// closed 21D50 census contract. Generation must fail on every acceptance
// failure mode:
//
//   target           target metadata differs from iPhone15,2 / 17.3 / 21D50
//   seed             seed digests do not match the immutable input reference
//   count            record counts differ from the census (30/32/13 eligible)
//   id               duplicated, omitted, malformed, or unknown module/
//                    capability IDs
//   ownership        capability/module ownership is inconsistent (cross-module
//                    references, local-index gaps, unlisted capabilities)
//   disposition      missing/unknown disposition, implicit eligibility default,
//                    stock-only record emitting a route, eligible record without
//                    family/recipe, or a seed-disposition mapping violation
//   alias            empty/duplicate alias set or an alias collision without
//                    explicit disambiguation
//   asset            eligible record without a validated required Plampy asset
//   family           Renderer Family with no typed adapter
//   evidence         dangling or incomplete lifecycle evidence; an eligible
//                    capability in the activation set without complete direct
//                    21D50 lifecycle evidence
//   selected-stage   missing stage selection (exactly one stage per artifact)
//   stage-name       unknown stage name
//   stage-duplicate  duplicated active ID inside the stage
//   stage-shape      wrong stage cardinality/content (Q0 empty, A1 exactly Low
//                    Power, A2 exactly the trio plus one concretely named
//                    button-host capability, A3/R1 exactly the eligible set)
//
// Catalog eligibility never requires lifecycle evidence: eligibility is a
// catalog fact, activation is an artifact fact. Missing lifecycle evidence
// leaves a catalog-eligible capability inactive and stock-forwarding.

import type {
  CapabilityId,
  CapabilityRecord,
  EvidenceDisposition,
  LifecycleEvidenceId,
  LifecycleEvidenceRecord,
  ModuleRecord,
  StageName,
  ThemeManifest,
} from "../../manifest/theme-manifest.ts";

export type ValidationCode =
  | "target"
  | "seed"
  | "count"
  | "id"
  | "ownership"
  | "disposition"
  | "alias"
  | "asset"
  | "family"
  | "evidence"
  | "selected-stage"
  | "stage-name"
  | "stage-duplicate"
  | "stage-shape";

export type ValidationIssue = {
  readonly code: ValidationCode;
  readonly message: string;
};

export type ValidationResult = {
  readonly ok: boolean;
  readonly errors: readonly ValidationIssue[];
};

// The closed 21D50 census contract. Pinned to the immutable canonical seed and
// the accepted 21D50 Plampy map (13 catalog-eligible CAML capability records).
export type CensusContract = {
  readonly target: {
    readonly productType: string;
    readonly productVersion: string;
    readonly build: string;
  };
  readonly moduleIds: readonly string[];
  readonly capabilityIds: readonly string[];
  readonly eligibleIds: readonly string[];
  readonly seedSha256: string;
  readonly sourceSha256: string;
};

export const CONTRACT_21D50: CensusContract = {
  target: { productType: "iPhone15,2", productVersion: "17.3", build: "21D50" },
  moduleIds: [
    "AccessibilityGuidedAccessControlCenterModule",
    "AccessibilityShorcutsModule",
    "AccessibilitySoundDetectionControlCenterModule",
    "AccessibilityTextSizeModule",
    "AirPlayMirroringModule",
    "AlarmModule",
    "AppearanceModule",
    "CalculatorModule",
    "CameraModule",
    "ConnectivityModule",
    "DisplayModule",
    "FlashlightModule",
    "FocusUI",
    "HearingAidsModule",
    "LowPowerModule",
    "MagnifierModule",
    "MediaControls",
    "MuteModule",
    "NFCControlCenterModule",
    "OrientationLockModule",
    "PerformanceTraceModule",
    "QRCodeModule",
    "ReplayKitModule",
    "ShazamModule",
    "SpringBoard_Ringer",
    "StopwatchModule",
    "TimerModule",
    "TVRemoteModule",
    "VoiceMemosModule",
    "WalletModule",
  ],
  capabilityIds: [
    "accessibility-guided-access",
    "accessibility-shortcuts",
    "accessibility-sound-detection",
    "accessibility-text-size",
    "airplay-mirroring",
    "alarm",
    "appearance",
    "calculator",
    "camera",
    "connectivity-caml",
    "connectivity-glyphs",
    "display-brightness",
    "display-catalog",
    "flashlight",
    "focus",
    "hearing-aids",
    "low-power",
    "magnifier",
    "media-controls-volume",
    "mute",
    "nfc",
    "orientation-lock",
    "performance-trace",
    "qr-code",
    "replaykit",
    "shazam",
    "springboard-ringer",
    "stopwatch",
    "timer",
    "tv-remote",
    "voice-memos",
    "wallet",
  ],
  eligibleIds: [
    "airplay-mirroring",
    "appearance",
    "connectivity-caml",
    "display-brightness",
    "focus",
    "low-power",
    "media-controls-volume",
    "mute",
    "orientation-lock",
    "replaykit",
    "shazam",
    "springboard-ringer",
    "timer",
  ],
  seedSha256: "63252e96ade77361484a75eade500bc7a653965ead644f11eaffe02cc2a7ef99",
  sourceSha256: "d1d990e14cbbb683cfd5a42a924ec1839303e1cc4499bf0c976e89c9aabd9919",
};

// Stage shapes are contract constants of the artifact series, not of one
// artifact. Only the selected stage becomes the artifact's closed activation
// set (and therefore the only stage that requires complete lifecycle evidence).
export const STAGE_CARDINALITY: Readonly<Record<StageName, number | "eligible-set">> = {
  Q0: 0,
  A1: 1,
  A2: 4,
  A3: "eligible-set",
  R1: "eligible-set",
};

export const A1_FIXED: readonly string[] = ["low-power"];
export const A2_FIXED_TRIO: readonly string[] = [
  "low-power",
  "display-brightness",
  "media-controls-volume",
];

const DISPOSITIONS: readonly string[] = [
  "eligible",
  "stock-only-opaque",
  "stock-only-static",
  "stock-only-inferred",
  "stock-only-unknown",
  "stock-only-missing",
];

const STAGE_NAMES: readonly string[] = ["Q0", "A1", "A2", "A3", "R1"];

const MODULE_ID_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const CAPABILITY_ID_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export type ValidateOptions = {
  readonly contract?: CensusContract;
  readonly assetExists?: (path: string) => boolean;
};

type Mutable = Record<string, unknown>;

const isObject = (value: unknown): value is Mutable =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((entry) => isString(entry));

// Deterministic seed-disposition mapping (see manifest/theme-manifest.ts).
export function expectedDisposition(
  seedDisposition: string,
  seedEvidenceType: string,
  moduleRendererEvidenceStatus: string,
): string | null {
  switch (seedDisposition) {
    case "verified_asset_candidate":
      return "eligible";
    case "unknown_renderer_stock":
      return "stock-only-unknown";
    case "missing_asset_stock":
      return moduleRendererEvidenceStatus === "inferred"
        ? "stock-only-inferred"
        : "stock-only-missing";
    case "unresolved_catalog_stock":
      return seedEvidenceType === "static_png"
        ? "stock-only-static"
        : seedEvidenceType === "unknown"
          ? "stock-only-opaque"
          : null;
    default:
      return null;
  }
}

export function isLifecycleEvidenceComplete(record: unknown): boolean {
  if (!isObject(record)) return false;
  const strings = [
    "id",
    "module",
    "capability",
    "ownerClass",
    "hostClass",
    "bindSelector",
    "closeSignal",
    "detachSignal",
    "reuseSignal",
    "epochInvalidation",
    "producerTagPath",
    "stockCapturePath",
    "newerStockAdoptionPath",
    "restorationPath",
    "teardownPath",
    "missingFactCondition",
  ];
  for (const key of strings) {
    if (!isString(record[key]) || record[key].length === 0) return false;
  }
  const encodings = record.selectorEncodings;
  if (!isObject(encodings) || Object.keys(encodings).length === 0) return false;
  for (const [selector, encoding] of Object.entries(encodings)) {
    if (!isString(selector) || selector.length === 0) return false;
    if (!isString(encoding) || encoding.length === 0) return false;
  }
  const callSites = record.callSiteSources;
  return (
    isStringArray(callSites) &&
    callSites.length > 0 &&
    callSites.every((source) => source.length > 0)
  );
}

export function validateManifest(
  input: unknown,
  options: ValidateOptions = {},
): ValidationResult {
  const contract = options.contract ?? CONTRACT_21D50;
  const assetExists = options.assetExists ?? (() => true);
  const errors: ValidationIssue[] = [];
  const fail = (code: ValidationCode, message: string) => {
    errors.push({ code, message });
  };

  if (!isObject(input)) {
    fail("id", "manifest is not an object");
    return { ok: false, errors };
  }
  const manifest = input as unknown as ThemeManifest & Mutable;

  // ---- schema + target + seed -------------------------------------------------
  if (manifest.schema !== "plampycc-theme-manifest/v1") {
    fail("id", `unknown manifest schema: ${String(manifest.schema)}`);
  }
  const target = manifest.target;
  if (
    !isObject(target) ||
    target.productType !== contract.target.productType ||
    target.productVersion !== contract.target.productVersion ||
    target.build !== contract.target.build
  ) {
    fail(
      "target",
      `target metadata must be exactly ${contract.target.productType} / ${contract.target.productVersion} / ${contract.target.build}`,
    );
  }
  const seedRef = manifest.seed;
  if (
    !isObject(seedRef) ||
    seedRef.sha256 !== contract.seedSha256 ||
    seedRef.sourceSha256 !== contract.sourceSha256
  ) {
    fail("seed", "seed digests do not match the immutable input reference");
  }

  // ---- module records --------------------------------------------------------
  const modules: unknown[] = Array.isArray(manifest.modules) ? manifest.modules : [];
  const capabilities: unknown[] = Array.isArray(manifest.capabilities)
    ? manifest.capabilities
    : [];
  const adapters: unknown[] = Array.isArray(manifest.rendererFamilyAdapters)
    ? manifest.rendererFamilyAdapters
    : [];
  const evidenceRecords: Mutable = isObject(manifest.lifecycleEvidenceRecords)
    ? manifest.lifecycleEvidenceRecords
    : {};

  const moduleIds = modules.map((entry) =>
    isObject(entry) && isString(entry.id) ? entry.id : "",
  );
  const capabilityIds = capabilities.map((entry) =>
    isObject(entry) && isString(entry.id) ? entry.id : "",
  );

  if (modules.length !== contract.moduleIds.length) {
    fail("count", `expected ${contract.moduleIds.length} Module records, found ${modules.length}`);
  }
  if (capabilities.length !== contract.capabilityIds.length) {
    fail(
      "count",
      `expected ${contract.capabilityIds.length} Capability records, found ${capabilities.length}`,
    );
  }

  for (const moduleId of moduleIds) {
    if (!MODULE_ID_PATTERN.test(moduleId)) fail("id", `malformed Module ID: ${moduleId}`);
  }
  for (const capabilityId of capabilityIds) {
    if (!CAPABILITY_ID_PATTERN.test(capabilityId)) {
      fail("id", `malformed Capability ID: ${capabilityId}`);
    }
  }
  if (new Set(moduleIds).size !== moduleIds.length) fail("id", "duplicate Module ID");
  if (new Set(capabilityIds).size !== capabilityIds.length) fail("id", "duplicate Capability ID");

  const expectedModules = new Set(contract.moduleIds);
  for (const moduleId of moduleIds) {
    if (moduleId && !expectedModules.has(moduleId)) {
      fail("id", `module omitted from or unknown to the census: ${moduleId}`);
    }
  }
  for (const moduleId of contract.moduleIds) {
    if (!moduleIds.includes(moduleId)) fail("id", `module omitted from the census: ${moduleId}`);
  }
  const expectedCapabilities = new Set(contract.capabilityIds);
  for (const capabilityId of capabilityIds) {
    if (capabilityId && !expectedCapabilities.has(capabilityId)) {
      fail("id", `capability omitted from or unknown to the census: ${capabilityId}`);
    }
  }
  for (const capabilityId of contract.capabilityIds) {
    if (!capabilityIds.includes(capabilityId)) {
      fail("id", `capability omitted from the census: ${capabilityId}`);
    }
  }

  // ---- adapters (Renderer Family must have a typed adapter) ------------------
  const adapterFamilies = new Map<string, unknown>();
  for (const adapter of adapters) {
    if (!isObject(adapter) || !isString(adapter.family)) {
      fail("family", "malformed Renderer Family adapter declaration");
      continue;
    }
    adapterFamilies.set(adapter.family, adapter);
    const seams = Array.isArray(adapter.seams) ? adapter.seams : [];
    if (!isString(adapter.adapter) || adapter.adapter.length === 0 || seams.length === 0) {
      fail("family", `Renderer Family ${adapter.family} lacks a typed adapter`);
      continue;
    }
    for (const seam of seams) {
      if (
        !isObject(seam) ||
        !isString(seam.name) ||
        seam.name.length === 0 ||
        !isString(seam.ownerClass) ||
        seam.ownerClass.length === 0 ||
        !isString(seam.selector) ||
        seam.selector.length === 0 ||
        !isString(seam.encoding) ||
        seam.encoding.length === 0 ||
        !isString(seam.predecessorType) ||
        seam.predecessorType.length === 0
      ) {
        fail("family", `Renderer Family ${adapter.family} has an untyped seam declaration`);
      }
    }
  }

  // ---- capability records ----------------------------------------------------
  const capabilityById = new Map<string, Mutable>();
  const aliasOwners = new Map<string, Mutable[]>();
  const eligibleIds: string[] = [];

  for (const entry of capabilities) {
    if (!isObject(entry)) {
      fail("id", "capability record is not an object");
      continue;
    }
    const capability = entry;
    const capabilityId = isString(capability.id) ? capability.id : "";
    capabilityById.set(capabilityId, capability);

    const disposition = capability.disposition;
    if (!isString(disposition) || !DISPOSITIONS.includes(disposition)) {
      fail("disposition", `capability ${capabilityId} has missing or unknown disposition`);
      continue;
    }
    const seedDisposition = capability.seedDisposition;
    const seedEvidenceType = capability.seedEvidenceType;

    // Ownership: module back-reference and contiguous local index.
    const owningModule = modules.find(
      (moduleEntry) =>
        isObject(moduleEntry) &&
        Array.isArray(moduleEntry.capabilities) &&
        moduleEntry.capabilities.includes(capabilityId),
    ) as ModuleRecord | undefined;
    if (!isObject(owningModule) || owningModule.id !== capability.module) {
      fail(
        "ownership",
        `capability ${capabilityId} references Module Identity ${String(capability.module)} that does not own it`,
      );
    } else {
      const index = owningModule.capabilities.indexOf(capabilityId as CapabilityId);
      if (capability.localIndex !== index) {
        fail(
          "ownership",
          `capability ${capabilityId} localIndex ${String(capability.localIndex)} does not match its module position ${index}`,
        );
      }
    }

    // Seed disposition mapping must hold exactly.
    const moduleStatus = isObject(owningModule)
      ? String((owningModule as unknown as Mutable).seedRendererEvidenceStatus)
      : "";
    const mapped = expectedDisposition(
      isString(seedDisposition) ? seedDisposition : "",
      isString(seedEvidenceType) ? seedEvidenceType : "",
      moduleStatus,
    );
    if (mapped === null) {
      fail("disposition", `capability ${capabilityId} has unknown seed disposition mapping`);
    } else if (mapped !== disposition) {
      fail(
        "disposition",
        `capability ${capabilityId} disposition ${disposition} violates the seed mapping (expected ${mapped})`,
      );
    }

    // Aliases.
    const aliases = capability.stockAliases;
    if (!isStringArray(aliases)) {
      fail("alias", `capability ${capabilityId} has a malformed alias set`);
    } else {
      if (new Set(aliases).size !== aliases.length) {
        fail("alias", `capability ${capabilityId} has duplicate aliases`);
      }
      for (const alias of aliases) {
        if (alias.length === 0) fail("alias", `capability ${capabilityId} has an empty alias`);
        const owners = aliasOwners.get(alias) ?? [];
        owners.push(capability);
        aliasOwners.set(alias, owners);
      }
    }
    if (!isStringArray(capability.stockAssets)) {
      fail("id", `capability ${capabilityId} has a malformed stock asset list`);
    }
    if (
      !isObject(capability.deviceVector) ||
      !isStringArray(capability.deviceVector.visibleStates) ||
      capability.deviceVector.visibleStates.length === 0 ||
      !Array.isArray(capability.deviceVector.presentations) ||
      capability.deviceVector.presentations.length === 0 ||
      !capability.deviceVector.presentations.every(
        (presentation: unknown) => presentation === "compact" || presentation === "expanded",
      )
    ) {
      fail("id", `capability ${capabilityId} has a malformed device test vector`);
    }

    // Eligibility: explicit, never defaulted. Eligible records need a verified
    // Renderer Family, a route, and validated assets; stock-only records emit
    // nothing.
    const family = capability.rendererFamily;
    const recipe = capability.plampyRecipe;
    if (disposition === "eligible") {
      eligibleIds.push(capabilityId);
      if (!isString(family) || !adapterFamilies.has(family)) {
        fail(
          "family",
          `eligible capability ${capabilityId} names Renderer Family ${String(family)} with no typed adapter`,
        );
      }
      if (!isObject(recipe) || !Array.isArray(recipe.packages) || recipe.packages.length === 0) {
        fail("disposition", `eligible capability ${capabilityId} lacks a Plampy recipe`);
        continue;
      }
      for (const route of recipe.packages) {
        if (
          !isObject(route) ||
          !isString(route.packageName) ||
          route.packageName.length === 0 ||
          !isString(route.bundleDir) ||
          route.bundleDir.length === 0
        ) {
          fail("disposition", `eligible capability ${capabilityId} emits a malformed route`);
          continue;
        }
        if (isStringArray(aliases) && !aliases.includes(route.packageName)) {
          fail("alias", `route package ${route.packageName} is not a declared alias of ${capabilityId}`);
        }
        const expectedAsset = `layout/Library/Application Support/PlampyCC/Plampy/Assets/${route.bundleDir}/${route.packageName}.ca/main.caml`;
        if (route.requiredAsset !== expectedAsset) {
          fail(
            "asset",
            `eligible capability ${capabilityId} required asset must be ${expectedAsset}`,
          );
        } else if (!assetExists(route.requiredAsset)) {
          fail("asset", `eligible capability ${capabilityId} required asset is missing: ${route.requiredAsset}`);
        }
      }
    } else {
      if (family !== null && family !== undefined) {
        fail("family", `stock-only capability ${capabilityId} names a Renderer Family`);
      }
      if (recipe !== null && recipe !== undefined) {
        fail("disposition", `stock-only capability ${capabilityId} emits a replacement route`);
      }
    }
  }

  // Alias collisions require explicit disambiguation on every colliding record.
  for (const [alias, owners] of aliasOwners) {
    if (owners.length < 2) continue;
    const resolutions = owners.map((owner) => {
      const disambiguation = owner.aliasDisambiguation;
      if (
        isObject(disambiguation) &&
        disambiguation.alias === alias &&
        isString(disambiguation.resolution) &&
        disambiguation.resolution.length > 0 &&
        isString(disambiguation.rationale) &&
        disambiguation.rationale.length > 0
      ) {
        return disambiguation.resolution;
      }
      return null;
    });
    if (resolutions.some((resolution) => resolution === null)) {
      fail("alias", `alias ${alias} collides across records without explicit disambiguation`);
    } else if (new Set(resolutions).size !== resolutions.length) {
      fail("alias", `alias ${alias} collides with non-distinct disambiguations`);
    }
  }

  // ---- census counts and the accepted 21D50 Plampy map ----------------------
  const eligibleSet = new Set(eligibleIds);
  if (eligibleSet.size !== contract.eligibleIds.length) {
    fail(
      "count",
      `expected ${contract.eligibleIds.length} eligible CAML routes, found ${eligibleSet.size}`,
    );
  }
  for (const eligibleId of contract.eligibleIds) {
    if (!eligibleSet.has(eligibleId)) fail("id", `eligible route omitted: ${eligibleId}`);
  }
  for (const eligibleId of eligibleIds) {
    if (!contract.eligibleIds.includes(eligibleId)) {
      fail("id", `unexpected eligible route: ${eligibleId}`);
    }
  }
  const stockOnlyCount = capabilities.length - eligibleSet.size;
  if (stockOnlyCount !== contract.capabilityIds.length - contract.eligibleIds.length) {
    fail("count", `expected ${contract.capabilityIds.length - contract.eligibleIds.length} stock-only records, found ${stockOnlyCount}`);
  }

  // ---- lifecycle evidence ----------------------------------------------------
  for (const [evidenceId, record] of Object.entries(evidenceRecords)) {
    if (!isLifecycleEvidenceComplete(record)) {
      fail("evidence", `lifecycle evidence record ${evidenceId} is incomplete`);
    }
  }
  for (const entry of capabilities) {
    if (!isObject(entry)) continue;
    const reference = entry.lifecycleEvidence;
    if (reference === null || reference === undefined) continue;
    if (!isString(reference) || !isObject(evidenceRecords[reference])) {
      fail("evidence", `capability ${String(entry.id)} references dangling lifecycle evidence ${String(reference)}`);
      continue;
    }
    const record = evidenceRecords[reference] as unknown as LifecycleEvidenceRecord;
    if (record.capability !== entry.id || record.module !== entry.module) {
      fail("evidence", `lifecycle evidence ${reference} does not own capability ${String(entry.id)}`);
    }
  }

  // ---- selected stage (exactly one per artifact) -----------------------------
  const stage = manifest.selectedStage;
  if (!isObject(stage)) {
    fail("selected-stage", "exactly one stage must be selected per artifact");
    return { ok: ok(errors), errors };
  }
  const stageName = stage.name;
  if (!isString(stageName) || !STAGE_NAMES.includes(stageName)) {
    fail("stage-name", `unknown stage name: ${String(stageName)}`);
    return { ok: ok(errors), errors };
  }
  const active = Array.isArray(stage.activeCapabilities) ? stage.activeCapabilities : [];
  if (!isStringArray(active)) {
    fail("stage-shape", "stage activation set is malformed");
    return { ok: ok(errors), errors };
  }
  if (new Set(active).size !== active.length) {
    fail("stage-duplicate", `stage ${stageName} contains a duplicated active ID`);
  }
  for (const activeId of active) {
    if (!capabilityById.has(activeId)) {
      fail("stage-shape", `stage ${stageName} names a placeholder or unknown capability: ${activeId}`);
    }
  }

  const activeSet = new Set(active);
  const sameSet = (expected: readonly string[]): boolean =>
    activeSet.size === expected.length && expected.every((id) => activeSet.has(id));

  const cardinality = STAGE_CARDINALITY[stageName as StageName];
  const expectedCardinality =
    cardinality === "eligible-set" ? contract.eligibleIds.length : cardinality;
  if (active.length !== expectedCardinality) {
    fail(
      "stage-shape",
      `stage ${stageName} must contain ${expectedCardinality} active capabilities, found ${active.length}`,
    );
  }
  if (stageName === "Q0" && active.length !== 0) {
    fail("stage-shape", "Q0 must have an empty activation set");
  }
  if (stageName === "A1" && !sameSet(A1_FIXED)) {
    fail("stage-shape", "A1 must be exactly Low Power");
  }
  if (stageName === "A2") {
    const pilot = active.find((id) => !A2_FIXED_TRIO.includes(id));
    const trioPresent = A2_FIXED_TRIO.every((id) => activeSet.has(id));
    if (!trioPresent || pilot === undefined) {
      fail(
        "stage-shape",
        "A2 must be exactly Low Power, Display Brightness, Media Controls Volume, and one concretely selected button-host capability",
      );
    } else {
      const pilotRecord = capabilityById.get(pilot);
      if (
        !isObject(pilotRecord) ||
        pilotRecord.disposition !== "eligible" ||
        pilotRecord.hostForm !== "button-host"
      ) {
        fail(
          "stage-shape",
          `A2 pilot ${pilot} must be a concretely named catalog-eligible button-host capability (not a placeholder)`,
        );
      }
    }
  }
  if ((stageName === "A3" || stageName === "R1") && !sameSet(contract.eligibleIds)) {
    fail("stage-shape", `${stageName} must contain exactly the 13 eligible capabilities`);
  }

  // Activation gate: only eligible capabilities with complete direct 21D50
  // lifecycle evidence may enter the artifact's closed activation set.
  for (const activeId of active) {
    const record = capabilityById.get(activeId);
    if (!isObject(record)) continue;
    if (record.disposition !== "eligible") {
      fail("stage-shape", `activation set contains stock-only capability ${activeId}`);
      continue;
    }
    const reference = record.lifecycleEvidence;
    const evidence = isString(reference) ? evidenceRecords[reference] : undefined;
    if (!isLifecycleEvidenceComplete(evidence)) {
      fail(
        "evidence",
        `activated capability ${activeId} lacks complete direct 21D50 lifecycle evidence`,
      );
    }
  }

  return { ok: ok(errors), errors };
}

const ok = (errors: readonly ValidationIssue[]): boolean => errors.length === 0;

export function assertValidManifest(input: unknown, options: ValidateOptions = {}): void {
  const result = validateManifest(input, options);
  if (!result.ok) {
    const detail = result.errors.map((error) => `[${error.code}] ${error.message}`).join("\n");
    throw new Error(`theme manifest validation failed:\n${detail}`);
  }
}

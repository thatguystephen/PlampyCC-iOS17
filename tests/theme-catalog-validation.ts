// Validation gate: every generation-failure mode from the M0 acceptance
// contract, the stage-shape rules, the structural lifecycle-evidence gates,
// the closed renderer-family set, duplicate ownership membership, string
// safety, and the existing-family extension fixture (which now compiles AND
// runs the extended generated header). Each invalid fixture must fail
// generation with its expected error code; the positive fixtures (disambiguated
// alias collision, complete direct-21d50 activation, existing-family extension)
// must succeed.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { manifest } from "../manifest/theme-manifest.ts";
import {
  CONTRACT_21D50,
  validateManifest,
  validateSelectorEncoding,
  selectorArgumentCount,
  parseMethodEncoding,
  type CensusContract,
  type ValidationCode,
  type ValidationResult,
} from "../tools/theme-catalog/validate.ts";
import { renderCatalog } from "../tools/theme-catalog/generate.ts";
import {
  buildEvidence,
  byCapability,
  byModule,
  cloneManifest,
  type MutableManifest,
} from "./theme-manifest-fixtures.ts";

const root = fileURLToPath(new URL("../", import.meta.url));

const fail = (message: string): never => {
  throw new Error(message);
};
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message);
}

const validAssetExists = (): boolean => true;
const EXT_ASSET =
  "layout/Library/Application Support/PlampyCC/Plampy/Assets/FixtureExtraModule.bundle/FixtureExtra.ca/main.caml";

function validate(
  mutate: (copy: MutableManifest) => void,
  options: { assetExists?: (path: string) => boolean } = {},
): ValidationResult {
  const copy = cloneManifest();
  mutate(copy);
  return validateManifest(copy, {
    contract: CONTRACT_21D50,
    assetExists: validAssetExists,
    ...options,
  });
}

function expect(
  code: ValidationCode,
  mutate: (copy: MutableManifest) => void,
  options: { assetExists?: (path: string) => boolean } = {},
): void {
  const result = validate(mutate, options);
  assert(!result.ok, `fixture should fail: [${code}]`);
  assert(
    result.errors.some((error) => error.code === code),
    `expected ${code} in ${JSON.stringify(result.errors)}`,
  );
}

// ---- counts ----
expect("count", (copy) => copy.modules.pop()); // 29 modules
expect("count", (copy) => copy.capabilities.push(byCapability(copy, "alarm"))); // 33 caps
expect("count", (copy) => {
  const alarm = byCapability(copy, "alarm");
  alarm.disposition = "eligible";
  alarm.rendererFamily = "caml-package-setter";
  alarm.hostForm = "button-host";
  alarm.seedDisposition = "verified_asset_candidate";
  alarm.seedEvidenceType = "animated_caml";
  alarm.plampyRecipe = {
    packages: [
      {
        packageName: "Alarm",
        bundleDir: "AlarmModule.bundle",
        requiredAsset: "layout/Library/Application Support/PlampyCC/Plampy/Assets/AlarmModule.bundle/Alarm.ca/main.caml",
      },
    ],
  };
  alarm.stockAliases = ["Alarm"];
}); // 14 eligible
expect("count", (copy) => {
  const timer = byCapability(copy, "timer");
  timer.disposition = "stock-only-unknown";
  timer.seedDisposition = "unknown_renderer_stock";
  timer.seedEvidenceType = "unknown";
  timer.rendererFamily = null;
  timer.plampyRecipe = null;
}); // 12 eligible

// ---- ids ----
expect("id", (copy) => {
  byCapability(copy, "alarm").id = "airplay-mirroring"; // duplicate
});
expect("id", (copy) => {
  byCapability(copy, "alarm").id = "Bad ID!"; // malformed
});
expect("id", (copy) => {
  copy.capabilities.shift(); // omission -> 31 caps (and count)
});

// ---- ownership ----
expect("ownership", (copy) => {
  byCapability(copy, "alarm").module = "WalletModule"; // cross-module reference
});
expect("ownership", (copy) => {
  byCapability(copy, "alarm").localIndex = 5; // index gap vs module position
});
expect("ownership", (copy) => {
  byModule(copy, "AlarmModule").capabilities = []; // module no longer lists its capability
});
// Duplicate membership: the same capability in one module's list more than once.
expect("ownership", (copy) => {
  byModule(copy, "AlarmModule").capabilities = ["alarm", "alarm"];
});
// Duplicate ownership across module lists: one capability in two modules.
expect("ownership", (copy) => {
  byModule(copy, "WalletModule").capabilities.push("alarm");
});
// Malformed module record: capability list is not an array.
expect("ownership", (copy) => {
  (byModule(copy, "AlarmModule") as { capabilities: unknown }).capabilities = "alarm";
});
// Malformed module record: safe default is not preserved as stock.
expect("id", (copy) => {
  byModule(copy, "AlarmModule").safeDefault = "theme";
});

// ---- dispositions ----
expect("disposition", (copy) => {
  byCapability(copy, "alarm").disposition = "eligible-ish"; // unknown value
});
expect("disposition", (copy) => {
  delete (byCapability(copy, "alarm") as { disposition?: string }).disposition; // implicit/missing default
});
expect("disposition", (copy) => {
  byCapability(copy, "airplay-mirroring").plampyRecipe = null; // eligible without recipe
});
expect("disposition", (copy) => {
  byCapability(copy, "alarm").plampyRecipe = {
    packages: [{ packageName: "Alarm", bundleDir: "AlarmModule.bundle", requiredAsset: "x" }],
  }; // stock-only emits route
});
expect("disposition", (copy) => {
  const timer = byCapability(copy, "timer");
  timer.seedDisposition = "unknown_renderer_stock"; // mapping violation (still eligible)
});

// ---- family / adapters ----
expect("family", (copy) => {
  const caps = byCapability(copy, "airplay-mirroring");
  caps.rendererFamily = "static-glyph-setter"; // no typed adapter
});
expect("family", (copy) => {
  const caps = byCapability(copy, "airplay-mirroring");
  caps.rendererFamily = null; // eligible without family
});
expect("family", (copy) => {
  byCapability(copy, "alarm").rendererFamily = "caml-package-setter"; // stock-only names family
});
expect("family", (copy) => {
  copy.rendererFamilyAdapters[0]!.seams[0]!.encoding = ""; // untyped seam
});
// Invented family name rejected even when accompanied by an adapter declaration.
expect("family", (copy) => {
  copy.rendererFamilyAdapters.push({
    family: "static-glyph-setter",
    adapter: "FooAdapter",
    seams: [
      { name: "x", ownerClass: "A", selector: "b:", encoding: "v24@0:8@16", predecessorType: "void (*)(id, SEL, id)" },
    ],
  });
});
// Duplicate adapter-family declaration.
expect("family", (copy) => {
  copy.rendererFamilyAdapters.push({ ...copy.rendererFamilyAdapters[0]! });
});
// Not the exact typed CAML adapter.
expect("family", (copy) => {
  copy.rendererFamilyAdapters[0]!.adapter = "OtherAdapter";
});
// Not the exact typed CAML seam declaration (changed encoding).
expect("family", (copy) => {
  copy.rendererFamilyAdapters[0]!.seams[0]!.encoding = "v32@0:8@16";
});
// Extra seam inflates the closed seam set.
expect("family", (copy) => {
  copy.rendererFamilyAdapters[0]!.seams.push({
    name: "extra-seam",
    ownerClass: "CCUISomething",
    selector: "setExtra:",
    encoding: "v24@0:8@16",
    predecessorType: "void (*)(id, SEL, id)",
  });
});

// ---- aliases ----
expect("alias", (copy) => {
  byCapability(copy, "airplay-mirroring").stockAliases.push("MPAVScreenMirroring"); // duplicate
});
expect("alias", (copy) => {
  byCapability(copy, "alarm").stockAliases = ["Mute"]; // collides with mute, no disambiguation
});
{
  // positive: explicit disambiguation resolves the collision
  const result = validate((copy) => {
    byCapability(copy, "alarm").stockAliases = ["Mute"];
    byCapability(copy, "alarm").aliasDisambiguation = {
      alias: "Mute",
      resolution: "AlarmModule.bundle",
      rationale: "fixture",
    };
    byCapability(copy, "mute").aliasDisambiguation = {
      alias: "Mute",
      resolution: "MuteModule.bundle",
      rationale: "fixture",
    };
  });
  assert(result.ok, `disambiguated alias collision should validate: ${JSON.stringify(result.errors)}`);
}

// ---- string safety (newlines/control characters rejected before embedding) ----
expect("string", (copy) => {
  byCapability(copy, "airplay-mirroring").stockAliases.push("bad\nname");
});
expect("string", (copy) => {
  byCapability(copy, "alarm").deviceVector.visibleStates.push("x\u0001y");
});

// ---- assets ----
expect("asset", (copy) => {
  byCapability(copy, "airplay-mirroring").plampyRecipe!.packages[0]!.requiredAsset =
    "layout/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml";
});
expect(
  "asset",
  (copy) => {
    byCapability(copy, "airplay-mirroring").plampyRecipe!.packages[0]!.requiredAsset =
      "layout/Library/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml";
  },
  {
    assetExists: (path) =>
      path !== "layout/Library/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml",
  },
);

// ---- target / seed ----
expect("target", (copy) => {
  copy.target.productVersion = "17.4";
});
expect("seed", (copy) => {
  copy.seed.sha256 = "deadbeef";
});

// ---- stage names / duplicates / shapes ----
expect("stage-name", (copy) => {
  copy.selectedStage.name = "X9";
});
expect("stage-duplicate", (copy) => {
  copy.selectedStage = {
    name: "A3",
    activeCapabilities: [...CONTRACT_21D50.eligibleIds.slice(0, -1), CONTRACT_21D50.eligibleIds[0]!],
  };
});
expect("stage-shape", (copy) => {
  copy.selectedStage = { name: "Q0", activeCapabilities: ["low-power"] }; // Q0 must be empty
});
expect("stage-shape", (copy) => {
  copy.selectedStage = { name: "A1", activeCapabilities: ["timer"] }; // A1 != Low Power
});
expect("stage-shape", (copy) => {
  copy.selectedStage = { name: "A2", activeCapabilities: ["low-power", "display-brightness", "media-controls-volume"] }; // wrong cardinality
});
expect("stage-shape", (copy) => {
  copy.selectedStage = {
    name: "A2",
    activeCapabilities: ["low-power", "display-brightness", "media-controls-volume", "a2-button-pilot"], // placeholder
  };
});
expect("stage-shape", (copy) => {
  copy.selectedStage = {
    name: "A2",
    activeCapabilities: ["low-power", "display-brightness", "media-controls-volume", "connectivity-caml"], // not button-host
  };
});
expect("stage-shape", (copy) => {
  copy.selectedStage = { name: "A1", activeCapabilities: ["flashlight"] }; // stock-only in activation
});
expect("stage-shape", (copy) => {
  copy.selectedStage = {
    name: "A3",
    activeCapabilities: [...CONTRACT_21D50.eligibleIds.slice(0, 12), "wallet"],
  };
});
expect("selected-stage", (copy) => {
  (copy as { selectedStage?: unknown }).selectedStage = undefined;
});

// ---- structural lifecycle evidence gates ----
expect("evidence", (copy) => {
  byCapability(copy, "low-power").lifecycleEvidence = "evidence:does-not-exist"; // dangling
});
expect("evidence", (copy) => {
  copy.selectedStage = { name: "A1", activeCapabilities: ["low-power"] }; // eligible but no evidence -> inactive
});
// Synthetic evidence proves schema shape but can never close activation.
expect("evidence", (copy) => {
  copy.lifecycleEvidenceRecords["evidence:low-power"] = buildEvidence("low-power", "LowPowerModule", "synthetic-fixture");
  byCapability(copy, "low-power").lifecycleEvidence = "evidence:low-power";
  copy.selectedStage = { name: "A1", activeCapabilities: ["low-power"] };
});
// Map key must equal record.id.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
  record.id = "evidence:other";
});
// Unknown evidence kind.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.evidenceKind = "maybe";
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// A lifecycle role is unrepresented.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.selectors = record.selectors.filter((selector) => selector.role !== "close");
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// A lifecycle role is duplicated.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.selectors[1]!.role = "bind";
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// A named selector lacks a matching encoding.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  const bind = record.selectors.find((selector) => selector.role === "bind");
  assert(bind !== undefined, "bind selector missing from fixture");
  bind.encoding = null;
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// Direct evidence whose source is not explicitly bound to 21D50.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.selectors[0]!.callSiteSource = "somewhere else";
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// Synthetic evidence claiming a direct 21D50 source.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule", "synthetic-fixture");
  record.selectors[0]!.callSiteSource = "21D50 leaked source";
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// Placeholder-only fact statement.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.facts[0]!.statement = "TODO";
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
// A required Issue #9 fact is missing.
expect("evidence", (copy) => {
  const record = buildEvidence("low-power", "LowPowerModule");
  record.facts = record.facts.filter((fact) => fact.fact !== "teardown");
  copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
});
{
  // positive: complete direct-21d50 evidence closes A2 (activation independent
  // of catalog eligibility; evidence is required only at activation).
  const result = validate((copy) => {
    for (const [capabilityId, moduleId] of [
      ["low-power", "LowPowerModule"],
      ["display-brightness", "DisplayModule"],
      ["media-controls-volume", "MediaControls"],
      ["mute", "MuteModule"],
    ] as const) {
      copy.lifecycleEvidenceRecords[`evidence:${capabilityId}`] = buildEvidence(capabilityId, moduleId);
      byCapability(copy, capabilityId).lifecycleEvidence = `evidence:${capabilityId}`;
    }
    copy.selectedStage = {
      name: "A2",
      activeCapabilities: ["low-power", "display-brightness", "media-controls-volume", "mute"],
    };
  });
  assert(result.ok, `complete direct evidence A2 should validate: ${JSON.stringify(result.errors)}`);
}

// ---- ABI-encoding adversarial fixtures (direct parser assertions) ----------
// Lifecycle selector evidence must be a real arm64 method signature matching
// the shape the typed evidence record declares, not a plausible token.
{
  assert(parseMethodEncoding("v24@0:8@16") !== null, "v24@0:8@16 must parse");
  assert(parseMethodEncoding("v16@0:8") !== null, "v16@0:8 must parse");
  assert(selectorArgumentCount("layoutSubviews") === 0, "0-colon selector must declare 0 arguments");
  assert(selectorArgumentCount("setGlyphPackageDescription:") === 1, "1-colon selector must declare 1 argument");
  assert(selectorArgumentCount("doThis:withThat:") === 2, "2-colon selector must declare 2 arguments");
  assert(selectorArgumentCount("viewWillMoveToWindow:nil") === null, "unterminated selector must be malformed");

  assert(validateSelectorEncoding("v24@0:8@16", "setGlyphPackageDescription:") === null, "valid bind encoding must be accepted");
  assert(validateSelectorEncoding("v16@0:8", "layoutSubviews") === null, "valid 0-arg encoding must be accepted");

  // Scalar/object tokens and bare types are not method signatures.
  for (const bad of ["i", "q", "v", "B", "@\"NSString\"", "@", ":"]) {
    assert(validateSelectorEncoding(bad, "layoutSubviews") !== null, `accepted non-signature encoding ${bad}`);
  }
  // Missing self / missing _cmd.
  assert(validateSelectorEncoding("v24:8@16", "setGlyphPackageDescription:") !== null, "accepted encoding without self");
  assert(validateSelectorEncoding("v24@0@16", "setGlyphPackageDescription:") !== null, "accepted encoding without _cmd");
  assert(validateSelectorEncoding("v16:8", "layoutSubviews") !== null, "accepted 0-arg encoding without self");
  assert(validateSelectorEncoding("v16@0", "layoutSubviews") !== null, "accepted 0-arg encoding without _cmd");
  // Wrong colon arity in both directions.
  assert(validateSelectorEncoding("v16@0:8", "setGlyphPackageDescription:") !== null, "accepted 0-arg encoding for a 1-colon selector");
  assert(validateSelectorEncoding("v24@0:8@16", "layoutSubviews") !== null, "accepted 1-arg encoding for a 0-colon selector");
  // Truncated / inconsistent frame, offsets, dangling type or offset.
  for (const bad of ["v24@0:8@", "v24@0", "v24", "v24@0:8@1", "v32@0:8@16", "v24@0:8@24"]) {
    assert(validateSelectorEncoding(bad, "setGlyphPackageDescription:") !== null, `accepted malformed encoding ${bad}`);
  }
  // Plausible-but-wrong explicit argument types.
  for (const bad of ["v24@0:8#16", "v24@0:8*16", "v24@0:8@?16", "v24@0:8:16", "v24@0:8q16", "v24@0:8^v16", "v24@0:8f16", "v24@0:8B16"]) {
    assert(validateSelectorEncoding(bad, "setGlyphPackageDescription:") !== null, `accepted wrong explicit argument type ${bad}`);
  }
}

// ---- ABI-encoding adversarial fixtures (end-to-end through validateManifest) ----
{
  const setBindEncoding = (copy: MutableManifest, encoding: string): void => {
    const record = buildEvidence("low-power", "LowPowerModule");
    const bind = record.selectors.find((selector) => selector.role === "bind");
    assert(bind !== undefined, "bind selector missing from fixture");
    bind.encoding = encoding;
    copy.lifecycleEvidenceRecords["evidence:low-power"] = record;
    byCapability(copy, "low-power").lifecycleEvidence = "evidence:low-power";
  };
  expect("evidence", (copy) => setBindEncoding(copy, "i")); // scalar-only token
  expect("evidence", (copy) => setBindEncoding(copy, "v24:8@16")); // missing self
  expect("evidence", (copy) => setBindEncoding(copy, "v24@0@16")); // missing _cmd
  expect("evidence", (copy) => setBindEncoding(copy, "v16@0:8")); // selector/encoding arity mismatch
  expect("evidence", (copy) => setBindEncoding(copy, "v24@0:8@")); // truncated
  expect("evidence", (copy) => setBindEncoding(copy, "v24@0:8#16")); // plausible-but-wrong argument type
}

// ---- ordinal reorder-safety (canonical emission) ---------------------------
// Manifest record order is not artifact identity. Swapping the first two
// capability (or module) records cannot produce a valid mismatched artifact:
// generation emits ordinal-indexed arrays in canonical census order, so a
// reorder is both valid AND byte-identical, and every emitted ordinal still
// resolves to the matching contract identity.
{
  const base = renderCatalog(manifest);
  const swapped = cloneManifest();
  const [first, second] = [swapped.capabilities[0]!, swapped.capabilities[1]!];
  swapped.capabilities[0] = second;
  swapped.capabilities[1] = first;
  const valid = validateManifest(swapped, { contract: CONTRACT_21D50, assetExists: validAssetExists });
  assert(valid.ok, `capability record reorder must remain valid: ${JSON.stringify(valid.errors)}`);
  const rerendered = renderCatalog(swapped);
  assert(rerendered.header === base.header, "capability reorder changed the header (canonical emission violated)");
  assert(rerendered.json === base.json, "capability reorder changed the JSON (canonical emission violated)");
  const sidecar = JSON.parse(rerendered.json) as {
    capabilities: Array<{ ordinal: number; id: string }>;
    modules: Array<{ id: string }>;
  };
  sidecar.capabilities.forEach((capability, index) => {
    assert(capability.ordinal === index, `capability ordinal drift at ${index}`);
    assert(
      capability.id === CONTRACT_21D50.capabilityIds[index],
      `capability ordinal ${index} resolved to the wrong identity ${capability.id}`,
    );
  });
  sidecar.modules.forEach((module, index) => {
    assert(module.id === CONTRACT_21D50.moduleIds[index], `module ordinal ${index} resolved to the wrong identity ${module.id}`);
  });
}
{
  const base = renderCatalog(manifest);
  const swapped = cloneManifest();
  const [first, second] = [swapped.modules[0]!, swapped.modules[1]!];
  swapped.modules[0] = second;
  swapped.modules[1] = first;
  const valid = validateManifest(swapped, { contract: CONTRACT_21D50, assetExists: validAssetExists });
  assert(valid.ok, `module record reorder must remain valid: ${JSON.stringify(valid.errors)}`);
  const rerendered = renderCatalog(swapped);
  assert(rerendered.header === base.header, "module reorder changed the header (canonical emission violated)");
  assert(rerendered.json === base.json, "module reorder changed the JSON (canonical emission violated)");
}

// ---- existing-family extension fixture ----
// Adding a proved existing-family module changes manifest/asset/generated
// inputs only; hook sources are never edited. The rendered extended header is
// compiled AND run, not merely string-compared.
{
  const extContract: CensusContract = {
    target: CONTRACT_21D50.target,
    moduleIds: [...CONTRACT_21D50.moduleIds, "FixtureExtraModule"],
    capabilityIds: [...CONTRACT_21D50.capabilityIds, "fixture-extra"],
    eligibleIds: [...CONTRACT_21D50.eligibleIds, "fixture-extra"],
    seedSha256: CONTRACT_21D50.seedSha256,
    sourceSha256: CONTRACT_21D50.sourceSha256,
  };
  const ext = cloneManifest();
  ext.modules.push({
    id: "FixtureExtraModule",
    safeDefault: "stock",
    seedRendererEvidenceStatus: "verified",
    capabilities: ["fixture-extra"],
  });
  ext.capabilities.push({
    id: "fixture-extra",
    module: "FixtureExtraModule",
    localIndex: 0,
    disposition: "eligible",
    seedDisposition: "verified_asset_candidate",
    seedEvidenceType: "animated_caml",
    rendererFamily: "caml-package-setter",
    hostForm: "button-host",
    stockAliases: ["FixtureExtra"],
    stockAssets: ["FixtureExtraModule.bundle/FixtureExtra.ca"],
    plampyRecipe: {
      packages: [
        { packageName: "FixtureExtra", bundleDir: "FixtureExtraModule.bundle", requiredAsset: EXT_ASSET },
      ],
    },
    lifecycleEvidence: "evidence:fixture-extra",
    deviceVector: { visibleStates: ["off", "on"], presentations: ["compact"] },
  });
  ext.lifecycleEvidenceRecords["evidence:fixture-extra"] = buildEvidence(
    "fixture-extra",
    "FixtureExtraModule",
    "synthetic-fixture",
  );

  // The extended manifest fails the closed 21D50 census contract.
  const closedResult = validateManifest(ext, {
    contract: CONTRACT_21D50,
    assetExists: validAssetExists,
  });
  assert(!closedResult.ok, "extended manifest must fail the closed 21D50 census contract");

  // Hash the hook sources so we can prove the extension never edits them.
  const hookSourceDir = join(root, "src");
  const hookSources = readdirSync(hookSourceDir)
    .filter((name) => /\.(xm|mm|hpp|h)$/.test(name))
    .filter((name) => name !== "PlampyCCThemeCatalog.hpp"); // generated output, not hook source
  const hookHash = () =>
    createHash("sha256")
      .update(JSON.stringify(hookSources.map((name) => readFileSync(join(hookSourceDir, name), "utf8"))))
      .digest("hex");
  const before = hookHash();

  // Under the extended census contract, generation succeeds and the generated
  // output changes — without touching hook source.
  const rendered = renderCatalog(ext, { contract: extContract, assetExists: validAssetExists });
  const checked = renderCatalog(manifest);
  assert(rendered.header !== checked.header, "extension must change generated output");
  assert(rendered.json !== checked.json, "extension must change generated JSON");
  assert(hookHash() === before, "extension changed hook source");

  // Compile AND run the extended rendered header (31 modules / 33 capabilities /
  // 14 eligible), proving the corrected emission compiles for any validated
  // census — the false-positive acceptance path this rework repairs.
  const compiler = ["g++", "c++"].find((candidate) => {
    const probe = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    return probe.status === 0;
  });
  assert(compiler !== undefined, "no C++ compiler available (g++/c++)");
  const scratch = mkdtempSync(join(tmpdir(), "plampycc-ext-"));
  try {
    writeFileSync(join(scratch, "PlampyCCThemeCatalog.hpp"), rendered.header);
    writeFileSync(join(scratch, "PlampyCCThemeCatalog.json"), rendered.json);
    const binary = join(scratch, "native-theme-catalog-extension");
    const compile = spawnSync(
      compiler,
      [
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-Werror",
        `-I${scratch}`,
        "-DEXPECT_MODULE_COUNT=31",
        "-DEXPECT_CAPABILITY_COUNT=33",
        "-DEXPECT_ELIGIBLE_COUNT=14",
        "-DEXPECT_ACTIVE_BITS=0",
        "tests/native-theme-catalog-extension.cpp",
        "-o",
        binary,
      ],
      { cwd: root, encoding: "utf8" },
    );
    assert(compile.status === 0, `extended native catalog compile failed:\n${compile.stderr}`);
    const run = spawnSync(binary, [], { encoding: "utf8" });
    assert(run.status === 0, `extended native catalog run failed:\n${run.stderr}`);
    assert(run.stdout.includes("PASS"), "extended native catalog did not print its PASS line");
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

console.log(
  "PASS: validation (invalid counts, IDs, ownership/membership, malformed module records, dispositions, aliases, assets, invented/duplicate adapter families, non-exact seams, target metadata, stage names, duplicate active IDs, wrong stage shapes, structural lifecycle-evidence mismatches, placeholder-only records, and control-character strings all fail generation; complete direct-21d50 evidence closes activation; existing-family extension compiles and runs the extended header without hook-source edits)",
);
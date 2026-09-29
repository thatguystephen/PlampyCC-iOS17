// Validation gate: every generation-failure mode from the M0 acceptance
// contract, plus the stage-shape rules and the existing-family extension
// fixture. Each invalid fixture must fail generation with its expected error
// code; the two positive fixtures (evidence-complete activation, existing
// family extension) must succeed.
//
// @ts-nocheck
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";

const root = decodeURIComponent(new URL("..", import.meta.url).pathname);
const { manifest } = await import(join(root, "manifest", "theme-manifest.ts"));
const { validateManifest, CONTRACT_21D50 } = await import(
  join(root, "tools", "theme-catalog", "validate.ts")
);
const { renderCatalog } = await import(join(root, "tools", "theme-catalog", "generate.ts"));

const fail = (message) => {
  throw new Error(message);
};
const assert = (condition, message) => {
  if (!condition) fail(message);
};

const clone = () => JSON.parse(JSON.stringify(manifest));
const validAssetExists = () => true;
const EXT_ASSET = "layout/Library/Application Support/PlampyCC/Plampy/Assets/FixtureExtraModule.bundle/FixtureExtra.ca/main.caml";

function validate(mutate, options = {}) {
  const copy = clone();
  mutate(copy);
  return validateManifest(copy, {
    contract: CONTRACT_21D50,
    assetExists: validAssetExists,
    ...options,
  });
}

function expect(code, mutate, options = {}) {
  const result = validate(mutate, options);
  assert(!result.ok, `fixture should fail: [${code}]`);
  assert(
    result.errors.some((error) => error.code === code),
    `expected ${code} in ${JSON.stringify(result.errors)}`,
  );
}

function byCapability(copy, id) {
  return copy.capabilities.find((capability) => capability.id === id);
}
function byModule(copy, id) {
  return copy.modules.find((module) => module.id === id);
}

const COMPLETE_EVIDENCE = (id = "low-power", module = "LowPowerModule") => ({
  id: `evidence:${id}`,
  module,
  capability: id,
  ownerClass: "owner",
  hostClass: module,
  bindSelector: "bind",
  closeSignal: "close",
  detachSignal: "detach",
  reuseSignal: "reuse",
  selectorEncodings: { "setGlyphPackageDescription:": "v24@0:8@16" },
  callSiteSources: ["21D50-call-site"],
  epochInvalidation: "invalidate-epoch",
  producerTagPath: "TagProducer",
  stockCapturePath: "CaptureStock",
  newerStockAdoptionPath: "AdoptNewer",
  restorationPath: "Restore",
  teardownPath: "TearDown",
  missingFactCondition: "missing-fact -> ForwardStock",
});

// ---- counts ----
expect("count", (copy) => copy.modules.pop()); // 29 modules
expect("count", (copy) => copy.capabilities.push(byCapability(copy, "alarm"))); // 33 caps
expect("count", (copy) => {
  const alarm = byCapability(copy, "alarm");
  alarm.disposition = "eligible";
  alarm.rendererFamily = "caml-package-setter";
  alarm.plampyRecipe = { packages: [{ packageName: "Alarm", bundleDir: "AlarmModule.bundle", requiredAsset: "layout/Library/Application Support/PlampyCC/Plampy/Assets/AlarmModule.bundle/Alarm.ca/main.caml" }] };
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
  const alarmModule = byModule(copy, "AlarmModule");
  alarmModule.capabilities = []; // module no longer lists its capability
});

// ---- dispositions ----
expect("disposition", (copy) => {
  byCapability(copy, "alarm").disposition = "eligible-ish"; // unknown value
});
expect("disposition", (copy) => {
  delete byCapability(copy, "alarm").disposition; // implicit/missing default
});
expect("disposition", (copy) => {
  const caps = byCapability(copy, "airplay-mirroring");
  caps.plampyRecipe = null; // eligible without recipe
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
  copy.rendererFamilyAdapters[0].seams[0].encoding = ""; // untyped seam
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

// ---- assets ----
expect("asset", (copy) => {
  byCapability(copy, "airplay-mirroring").plampyRecipe.packages[0].requiredAsset =
    "layout/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml";
});
expect(
  "asset",
  (copy) => {
    byCapability(copy, "airplay-mirroring").plampyRecipe.packages[0].requiredAsset =
      "layout/Library/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml";
  },
  { assetExists: (path) => path !== "layout/Library/Application Support/PlampyCC/Plampy/Assets/AirPlayMirroringModule.bundle/MPAVScreenMirroring.ca/main.caml" },
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
    activeCapabilities: [...CONTRACT_21D50.eligibleIds.slice(0, -1), CONTRACT_21D50.eligibleIds[0]],
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
  copy.selectedStage = undefined;
});

// ---- lifecycle evidence gates ----
expect("evidence", (copy) => {
  byCapability(copy, "low-power").lifecycleEvidence = "evidence:does-not-exist"; // dangling
});
expect("evidence", (copy) => {
  copy.selectedStage = { name: "A1", activeCapabilities: ["low-power"] }; // eligible but no evidence -> inactive
});
expect("evidence", (copy) => {
  copy.lifecycleEvidenceRecords["evidence:low-power"] = {
    ...COMPLETE_EVIDENCE(),
    bindSelector: "", // incomplete record
  };
  byCapability(copy, "low-power").lifecycleEvidence = "evidence:low-power";
  copy.selectedStage = { name: "A1", activeCapabilities: ["low-power"] };
});
{
  // positive: complete direct evidence closes A1 (activation independent of
  // catalog eligibility; evidence is required only at activation).
  const result = validate((copy) => {
    copy.lifecycleEvidenceRecords["evidence:low-power"] = COMPLETE_EVIDENCE();
    byCapability(copy, "low-power").lifecycleEvidence = "evidence:low-power";
    copy.selectedStage = { name: "A2", activeCapabilities: ["low-power", "display-brightness", "media-controls-volume", "mute"] };
    copy.lifecycleEvidenceRecords["evidence:mute"] = COMPLETE_EVIDENCE("mute", "MuteModule");
    copy.lifecycleEvidenceRecords["evidence:display-brightness"] = COMPLETE_EVIDENCE("display-brightness", "DisplayModule");
    copy.lifecycleEvidenceRecords["evidence:media-controls-volume"] = COMPLETE_EVIDENCE("media-controls-volume", "MediaControls");
    byCapability(copy, "mute").lifecycleEvidence = "evidence:mute";
    byCapability(copy, "display-brightness").lifecycleEvidence = "evidence:display-brightness";
    byCapability(copy, "media-controls-volume").lifecycleEvidence = "evidence:media-controls-volume";
  });
  assert(result.ok, `complete-evidence A2 should validate: ${JSON.stringify(result.errors)}`);
}

// ---- existing-family extension fixture ----
// Adding a proved existing-family module changes manifest/asset/generated
// inputs only; hook sources are never edited.
{
  const extContract = {
    target: CONTRACT_21D50.target,
    moduleIds: [...CONTRACT_21D50.moduleIds, "FixtureExtraModule"],
    capabilityIds: [...CONTRACT_21D50.capabilityIds, "fixture-extra"],
    eligibleIds: [...CONTRACT_21D50.eligibleIds, "fixture-extra"],
    seedSha256: CONTRACT_21D50.seedSha256,
    sourceSha256: CONTRACT_21D50.sourceSha256,
  };
  const ext = clone();
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
  ext.lifecycleEvidenceRecords["evidence:fixture-extra"] = COMPLETE_EVIDENCE("fixture-extra", "FixtureExtraModule");

  // The extended manifest fails the closed 21D50 census contract.
  const closedResult = validateManifest(ext, {
    contract: CONTRACT_21D50,
    assetExists: validAssetExists,
  });
  assert(!closedResult.ok, "extended manifest must fail the closed 21D50 census contract");

  // Hash the hook sources so we can prove the extension never edits them.
  const hookSourceDir = join(root, "src");
  const hookSources = readdirSync(hookSourceDir)
    .filter((name) => name.endsWith(".xm") || name.endsWith(".mm") || name.endsWith(".hpp") || name.endsWith(".h"))
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

  // Write the extended generated output to a scratch directory (never into the
  // repository) to prove the write side of the extension path.
  const scratch = mkdtempSync(join(tmpdir(), "plampycc-ext-"));
  try {
    writeFileSync(join(scratch, "PlampyCCThemeCatalog.hpp"), rendered.header);
    writeFileSync(join(scratch, "PlampyCCThemeCatalog.json"), rendered.json);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

console.log(
  "PASS: validation (invalid counts, IDs, ownership, dispositions, aliases, assets, family adapters, target metadata, stage names, duplicate active IDs, and wrong stage shapes all fail generation; complete 21D50 lifecycle evidence closes activation; existing-family extension changes only manifest/asset/generated inputs)",
);
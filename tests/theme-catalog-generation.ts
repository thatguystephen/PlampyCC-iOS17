// Generation gate: determinism, byte-identity with the checked-in output
// (stale-generation gate), generated-content shape, digest recomputation and
// catalog/activation digest independence, the CLI --check command, and the
// native C++17 compile/run of the generated immutable catalog.

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { manifest } from "../manifest/theme-manifest.ts";
import {
  computeDigests,
  escapeCString,
  renderCatalog,
} from "../tools/theme-catalog/generate.ts";
import { validateManifest } from "../tools/theme-catalog/validate.ts";
import { cloneManifest } from "./theme-manifest-fixtures.ts";

const root = fileURLToPath(new URL("../", import.meta.url));

const fail = (message: string): never => {
  throw new Error(message);
};
function assert(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message);
}

// ---- string escaping (defense in depth; validation rejects control chars) ----
assert(escapeCString('a"b\\c') === 'a\\"b\\\\c', `quote/backslash escape wrong: ${escapeCString('a"b\\c')}`);
assert(escapeCString("l1\nl2") === "l1\\nl2", "newline escape wrong");
assert(escapeCString("a\rb\tc") === "a\\rb\\tc", "CR/tab escape wrong");
assert(escapeCString("\u0001") === "\\001", "control escape wrong");
assert(escapeCString("plain") === "plain", "plain escape wrong");

// ---- validation of the canonical manifest ----
const validation = validateManifest(manifest);
assert(validation.ok, `canonical manifest must validate: ${JSON.stringify(validation.errors)}`);

// ---- determinism ----
const first = renderCatalog(manifest);
const second = renderCatalog(manifest);
assert(first.header === second.header, "header rendering is not deterministic");
assert(first.json === second.json, "JSON rendering is not deterministic");

// ---- byte-identity with checked-in output (stale-generation gate) ----
const headerPath = join(root, "src", "generated", "PlampyCCThemeCatalog.hpp");
const jsonPath = join(root, "src", "generated", "PlampyCCThemeCatalog.json");
const checkedHeader = readFileSync(headerPath, "utf8");
const checkedJson = readFileSync(jsonPath, "utf8");
assert(checkedHeader === first.header, "checked-in Objective-C++ catalog is stale");
assert(checkedJson === first.json, "checked-in JSON sidecar is stale");

// ---- CLI --check (the command the repo's verification surface invokes) ----
const check = spawnSync("bun", ["tools/theme-catalog/generate.ts", "--check"], {
  cwd: root,
  encoding: "utf8",
});
assert(check.status === 0, `generate --check failed: ${check.stderr}`);
assert(check.stdout.includes("PASS"), "generate --check did not print its PASS line");

// ---- digest recomputation round-trip against the JSON sidecar ----
const sidecar = JSON.parse(first.json) as {
  catalogDigest: string;
  activationSetDigest: string;
  counts: { modules: number; capabilities: number; eligible: number; stockOnly: number };
  selectedStage: { name: string; activeCapabilities: string[] };
  rendererFamilyAdapters: unknown[];
  lifecycleEvidence: unknown;
  capabilities: Array<Record<string, unknown>>;
};
const digests = computeDigests(manifest);
assert(sidecar.catalogDigest === `sha256:${digests.catalog}`, "catalog digest drifted");
assert(sidecar.activationSetDigest === `sha256:${digests.activationSet}`, "activation digest drifted");
assert(sidecar.counts.modules === 30, "sidecar module count wrong");
assert(sidecar.counts.capabilities === 32, "sidecar capability count wrong");
assert(sidecar.counts.eligible === 13, "sidecar eligible count wrong");
assert(sidecar.counts.stockOnly === 19, "sidecar stock-only count wrong");
assert(sidecar.selectedStage.name === "Q0", "selected stage is not Q0");
assert(sidecar.selectedStage.activeCapabilities.length === 0, "Q0 activation set is not empty");
// Host-test evidence metadata is emitted.
assert(
  Array.isArray(sidecar.rendererFamilyAdapters) && sidecar.rendererFamilyAdapters.length > 0,
  "sidecar does not emit renderer-adapter declarations",
);
assert(typeof sidecar.lifecycleEvidence === "object" && sidecar.lifecycleEvidence !== null, "sidecar does not emit lifecycle evidence metadata");

// ---- generated content shape ----
for (const capability of sidecar.capabilities) {
  assert(capability.disposition !== undefined, `capability ${capability.id} has no explicit disposition`);
  if (capability.disposition === "eligible") {
    assert(capability.rendererFamily === "caml-package-setter", `${capability.id} missing family`);
    assert(Array.isArray(capability.routes) && capability.routes.length > 0, `${capability.id} emits no route`);
    assert(Array.isArray(capability.stockAliases) && capability.stockAliases.length > 0, `${capability.id} has empty alias set`);
  } else {
    assert(capability.rendererFamily === null, `${capability.id} names a family`);
    assert(Array.isArray(capability.routes) && capability.routes.length === 0, `${capability.id} emits a replacement route`);
  }
  const vector = capability.deviceVector as { visibleStates: string[]; presentations: string[] };
  assert(vector.visibleStates.length > 0, `${capability.id} has no visible states`);
  assert(vector.presentations.length > 0, `${capability.id} has no presentation`);
  assert(capability.active === false, `${capability.id} is active under Q0`);
}

// ---- catalog vs activation identity are separate ----
{
  const base = computeDigests(manifest);

  // Activation-only change: same catalog identity, new activation identity.
  const activated = cloneManifest();
  activated.selectedStage = { name: "A1", activeCapabilities: ["low-power"] };
  const activationChanged = computeDigests(activated);
  assert(
    activationChanged.catalog === base.catalog,
    "changing the activation set changed the catalog digest",
  );
  assert(
    activationChanged.activationSet !== base.activationSet,
    "changing the activation set did not change the activation digest",
  );

  // Catalog-data change (a disposition is a catalog fact): catalog identity changes.
  const recategorized = cloneManifest();
  const alarm = recategorized.capabilities.find((capability) => capability.id === "alarm");
  assert(alarm !== undefined, "alarm capability missing from fixture");
  alarm.seedDisposition = "unresolved_catalog_stock";
  alarm.seedEvidenceType = "static_png";
  alarm.disposition = "stock-only-static";
  assert(computeDigests(recategorized).catalog !== base.catalog, "changing a catalog record did not change the catalog digest");

  // Evidence-data change: lifecycle evidence is generation-relevant.
  const withEvidence = cloneManifest();
  withEvidence.lifecycleEvidenceRecords["evidence:low-power"] = {
    id: "evidence:low-power",
    module: "LowPowerModule",
    capability: "low-power",
    evidenceKind: "synthetic-fixture",
    ownerClass: "LowPowerModule",
    hostClass: "HostOfLowPowerModule",
    selectors: [
      { role: "bind", form: "selector", name: "setGlyphPackageDescription:", encoding: "v24@0:8@16", callSiteSource: "synthetic bind source" },
      { role: "close", form: "signal", name: "moduleWillDisappear", encoding: null, callSiteSource: "synthetic close source" },
      { role: "detach", form: "signal", name: "viewWillMoveToWindow:nil", encoding: null, callSiteSource: "synthetic detach source" },
      { role: "reuse", form: "selector", name: "layoutSubviews", encoding: "v@8@0:8", callSiteSource: "synthetic reuse source" },
    ],
    facts: [
      { fact: "epoch-invalidation", statement: "invalidate epoch", source: "synthetic epoch source" },
      { fact: "producer-tag", statement: "tag producer", source: "synthetic producer source" },
      { fact: "stock-capture", statement: "capture stock", source: "synthetic capture source" },
      { fact: "newer-stock-adoption", statement: "adopt newer", source: "synthetic adoption source" },
      { fact: "restoration", statement: "restore stock", source: "synthetic restoration source" },
      { fact: "teardown", statement: "tear down", source: "synthetic teardown source" },
      { fact: "missing-fact-fail-open", statement: "forward stock", source: "synthetic fail-open source" },
    ],
  };
  assert(computeDigests(withEvidence).catalog !== base.catalog, "changing lifecycle evidence did not change the catalog digest");
  assert(computeDigests(withEvidence).activationSet === base.activationSet, "evidence change altered the activation digest");

  // Adapter-declaration change: renderer adapters are generation-relevant.
  const adapterChanged = cloneManifest();
  adapterChanged.rendererFamilyAdapters[0]!.adapter = "CAMLAdapter";
  adapterChanged.rendererFamilyAdapters[0]!.seams[0]!.encoding = "v32@0:8@16";
  assert(computeDigests(adapterChanged).catalog !== base.catalog, "changing a renderer adapter did not change the catalog digest");
}

// ---- native C++17 compile and run of the generated header ----
const compiler = ["g++", "c++"].find((candidate) => {
  const probe = spawnSync(candidate, ["--version"], { encoding: "utf8" });
  return probe.status === 0;
});
assert(compiler !== undefined, "no C++ compiler available (g++/c++)");
const scratch = mkdtempSync(join(tmpdir(), "plampycc-theme-catalog-"));
const binary = join(scratch, "native-theme-catalog");
try {
  const compile = spawnSync(
    compiler,
    ["-std=c++17", "-Wall", "-Wextra", "-Werror", "tests/native-theme-catalog.cpp", "-o", binary],
    { cwd: root, encoding: "utf8" },
  );
  assert(compile.status === 0, `native catalog compile failed:\n${compile.stderr}`);
  const run = spawnSync(binary, [], { encoding: "utf8" });
  assert(run.status === 0, `native catalog run failed:\n${run.stderr}`);
  assert(run.stdout.includes("PASS"), "native catalog did not print its PASS line");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

console.log(
  `PASS: generation (deterministic; checked-in output byte-identical; --check green; catalog/activation digests independent; evidence + adapter declarations in catalog identity; catalog ${digests.catalog}; activation ${digests.activationSet}; native C++17 compile + run green)`,
);
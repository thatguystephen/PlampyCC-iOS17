// Generation gate: determinism, byte-identity with the checked-in output
// (stale-generation gate), generated-content shape, digest recomputation, the
// CLI --check command, and the native C++17 compile/run of the generated
// immutable catalog.
//
// @ts-nocheck
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const root = decodeURIComponent(new URL("..", import.meta.url).pathname);
const { manifest } = await import(join(root, "manifest", "theme-manifest.ts"));
const { renderCatalog, computeDigests } = await import(
  join(root, "tools", "theme-catalog", "generate.ts")
);
const { validateManifest } = await import(join(root, "tools", "theme-catalog", "validate.ts"));

const fail = (message) => {
  throw new Error(message);
};
const assert = (condition, message) => {
  if (!condition) fail(message);
};
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

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
const sidecar = JSON.parse(first.json);
const digests = computeDigests(manifest);
assert(sidecar.catalogDigest === `sha256:${digests.catalog}`, "catalog digest drifted");
assert(sidecar.activationSetDigest === `sha256:${digests.activationSet}`, "activation digest drifted");
assert(sidecar.counts.modules === 30, "sidecar module count wrong");
assert(sidecar.counts.capabilities === 32, "sidecar capability count wrong");
assert(sidecar.counts.eligible === 13, "sidecar eligible count wrong");
assert(sidecar.counts.stockOnly === 19, "sidecar stock-only count wrong");
assert(sidecar.selectedStage.name === "Q0", "selected stage is not Q0");
assert(sidecar.selectedStage.activeCapabilities.length === 0, "Q0 activation set is not empty");

// ---- generated content shape ----
for (const capability of sidecar.capabilities) {
  assert(capability.disposition !== undefined, `capability ${capability.id} has no explicit disposition`);
  if (capability.disposition === "eligible") {
    assert(capability.rendererFamily === "caml-package-setter", `${capability.id} missing family`);
    assert(capability.routes.length > 0, `${capability.id} emits no route`);
    assert(capability.stockAliases.length > 0, `${capability.id} has empty alias set`);
  } else {
    assert(capability.rendererFamily === null, `${capability.id} names a family`);
    assert(capability.routes.length === 0, `${capability.id} emits a replacement route`);
  }
  assert(capability.deviceVector.visibleStates.length > 0, `${capability.id} has no visible states`);
  assert(capability.deviceVector.presentations.length > 0, `${capability.id} has no presentation`);
  assert(capability.active === false, `${capability.id} is active under Q0`);
}

// ---- native C++17 compile and run of the generated header ----
const compiler = ["g++", "c++"].find((candidate) => {
  const probe = spawnSync(candidate, ["--version"], { encoding: "utf8" });
  return probe.status === 0;
});
assert(compiler, "no C++ compiler available (g++/c++)");
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
  `PASS: generation (deterministic; checked-in output byte-identical; --check green; catalog ${digests.catalog}; activation ${digests.activationSet}; native C++17 compile + run green)`,
);
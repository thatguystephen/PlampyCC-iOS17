// PlampyCC theme catalog generator (M0).
//
// One deterministic operation: validate the checked-in manifest against the
// closed 21D50 census contract and emit the immutable Objective-C++ stock
// catalog plus the host/device evidence sidecar. The emitted runtime tables
// contain only closed IDs, precomputed tags, fixed alias/route sets, the
// selected activation bitset, and digests — no dynamic strings that require
// setter-time parsing. The shipping dylib contains no manifest parser.
//
// USAGE (from repo root):
//   bun tools/theme-catalog/generate.ts            # validate + write outputs
//   bun tools/theme-catalog/generate.ts --check    # fail unless outputs match
//
// Generation fails (nonzero exit) on any validation error or any byte
// difference between rendered and checked-in output (stale-generation gate).

// @ts-nocheck

import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CONTRACT_21D50,
  validateManifest,
  type CensusContract,
} from "./validate.ts";
import { manifest, type ThemeManifest } from "../../manifest/theme-manifest.ts";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HEADER_PATH = join(REPO_ROOT, "src", "generated", "PlampyCCThemeCatalog.hpp");
const JSON_PATH = join(REPO_ROOT, "src", "generated", "PlampyCCThemeCatalog.json");

// ---- deterministic helpers ---------------------------------------------------

type Capability = ThemeManifest["capabilities"][number];

function fnv1a32(input: string): number {
  let hash = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

const sha256Hex = (value: string): string => createHash("sha256").update(value).digest("hex");
const hex32 = (value: number): string => `0x${value.toString(16).padStart(8, "0")}u`;

function cString(value: string): string {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function capabilityEnumerator(id: string): string {
  return id
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function dispositionEnumerator(disposition: string): string {
  switch (disposition) {
    case "eligible":
      return "Eligible";
    case "stock-only-opaque":
      return "StockOnlyOpaque";
    case "stock-only-static":
      return "StockOnlyStatic";
    case "stock-only-inferred":
      return "StockOnlyInferred";
    case "stock-only-unknown":
      return "StockOnlyUnknown";
    case "stock-only-missing":
      return "StockOnlyMissing";
    default:
      throw new Error(`unknown disposition: ${disposition}`);
  }
}

// Canonical catalog serialization (seed order is canonical). A change to any
// record, route, alias, disposition, or the selected stage changes the catalog
// digest — which is the artifact identity.
function canonicalCatalog(input: ThemeManifest): Record<string, unknown> {
  return {
    schema: input.schema,
    target: input.target,
    selectedStage: input.selectedStage,
    modules: input.modules.map((module) => ({
      id: module.id,
      safeDefault: module.safeDefault,
      capabilities: module.capabilities,
    })),
    capabilities: input.capabilities.map((capability) => ({
      id: capability.id,
      module: capability.module,
      localIndex: capability.localIndex,
      disposition: capability.disposition,
      seedDisposition: capability.seedDisposition,
      seedEvidenceType: capability.seedEvidenceType,
      rendererFamily: capability.rendererFamily,
      hostForm: capability.hostForm,
      stockAliases: capability.stockAliases,
      stockAssets: capability.stockAssets,
      aliasDisambiguation: capability.aliasDisambiguation ?? null,
      lifecycleEvidence: capability.lifecycleEvidence,
      routes: capability.plampyRecipe
        ? capability.plampyRecipe.packages.map((route) => ({
            packageName: route.packageName,
            bundleDir: route.bundleDir,
            requiredAsset: route.requiredAsset,
          }))
        : null,
      deviceVector: capability.deviceVector,
    })),
  };
}

export function computeDigests(input: ThemeManifest): { catalog: string; activationSet: string } {
  const catalog = sha256Hex(JSON.stringify(canonicalCatalog(input)));
  const activationSet = sha256Hex(
    JSON.stringify({
      stage: input.selectedStage.name,
      activeCapabilities: input.selectedStage.activeCapabilities,
    }),
  );
  return { catalog, activationSet };
}

// ---- Objective-C++ rendering -------------------------------------------------

function renderHeader(
  input: ThemeManifest,
  contract: CensusContract,
  digests: { catalog: string; activationSet: string },
): string {
  const eligibleCount = contract.eligibleIds.length;
  const stockOnlyCount = contract.capabilityIds.length - eligibleCount;
  const bitset = input.selectedStage.activeCapabilities.reduce(
    (accumulator, id, ordinal) => accumulator | (1 << contract.capabilityIds.indexOf(id)),
    0,
  );
  const activeHex = hex32(bitset);
  const capabilities = input.capabilities;

  const lines: string[] = [];
  const push = (text: string) => lines.push(text);

  push("// GENERATED BY tools/theme-catalog/generate.ts — DO NOT EDIT BY HAND.");
  push("// Regenerate: bun tools/theme-catalog/generate.ts");
  push("// Verify:     bun tools/theme-catalog/generate.ts --check");
  push("// Source of truth: manifest/theme-manifest.ts, validated against");
  push("// manifest/21d50-canonical-manifest-seed.json (seed SHA-256");
  push(`// ${contract.seedSha256}; source ${contract.sourceSha256}).`);
  push(`// Immutable Q0 stock catalog for ${contract.target.productType} / ${contract.target.productVersion} / ${contract.target.build}:`);
  push(`// ${contract.moduleIds.length} module identities, ${contract.capabilityIds.length} capabilities, ${eligibleCount} eligible CAML`);
  push(`// routes, ${stockOnlyCount} stock-only dispositions, activation bitset ${activeHex}.`);
  push("// This header is constant C++17 data consumable from Objective-C++ translation units;");
  push("// it performs no parsing and allocates nothing.");
  push("#ifndef PLAMPYCC_GENERATED_THEME_CATALOG_HPP");
  push("#define PLAMPYCC_GENERATED_THEME_CATALOG_HPP");
  push("");
  push("#include <cstddef>");
  push("#include <cstdint>");
  push("");
  push("namespace plampycc {");
  push("namespace generated {");
  push("");
  push('inline constexpr char kSchema[] = "plampycc-theme-catalog/v1";');
  push(`inline constexpr char kTargetProductType[] = ${cString(contract.target.productType)};`);
  push(`inline constexpr char kTargetProductVersion[] = ${cString(contract.target.productVersion)};`);
  push(`inline constexpr char kTargetBuild[] = ${cString(contract.target.build)};`);
  push(`inline constexpr char kSelectedStage[] = ${cString(input.selectedStage.name)};`);
  push(`inline constexpr char kCatalogDigest[] = ${cString(`sha256:${digests.catalog}`)};`);
  push(`inline constexpr char kActivationSetDigest[] = ${cString(`sha256:${digests.activationSet}`)};`);
  push(`inline constexpr std::uint32_t kActiveCapabilityBits = ${activeHex};`);
  push(`inline constexpr std::size_t kModuleCount = ${contract.moduleIds.length};`);
  push(`inline constexpr std::size_t kCapabilityCount = ${contract.capabilityIds.length};`);
  push(`inline constexpr std::size_t kEligibleCount = ${eligibleCount};`);
  push(`inline constexpr std::size_t kStockOnlyCount = ${stockOnlyCount};`);
  push("");
  push("enum class ModuleId : std::uint16_t {");
  contract.moduleIds.forEach((moduleId, index) => {
    push(`  ${moduleId} = ${index},`);
  });
  push("};");
  push("");
  push("enum class CapabilityId : std::uint16_t {");
  contract.capabilityIds.forEach((capabilityId, index) => {
    push(`  ${capabilityEnumerator(capabilityId)} = ${index},`);
  });
  push("};");
  push("");
  push("enum class EvidenceDisposition : std::uint8_t {");
  push("  Eligible = 0,");
  push("  StockOnlyOpaque = 1,");
  push("  StockOnlyStatic = 2,");
  push("  StockOnlyInferred = 3,");
  push("  StockOnlyUnknown = 4,");
  push("  StockOnlyMissing = 5,");
  push("};");
  push("");
  push("struct StockAlias {");
  push("  const char *name;");
  push("};");
  push("");
  push("struct PackageRoute {");
  push("  const char *packageName;");
  push("  const char *bundleDir;");
  push("};");
  push("");
  push("struct CapabilityEntry {");
  push("  CapabilityId id;");
  push("  ModuleId module;");
  push("  const char *idString;");
  push("  EvidenceDisposition disposition;");
  push("  const char *rendererFamily;  // nullptr when no verified Renderer Family");
  push("  const char *lifecycleEvidenceId;  // nullptr until direct 21D50 evidence closes");
  push("  std::uint32_t tag;  // precomputed FNV-1a-32 capability tag");
  push("  std::uint32_t activeBit;  // 1u << ordinal; 0 outside the activation set");
  push("  bool eligible;");
  push("  const StockAlias *aliases;");
  push("  std::size_t aliasCount;");
  push("  const PackageRoute *routes;");
  push("  std::size_t routeCount;");
  push("  const char *const *visibleStates;");
  push("  std::size_t visibleStateCount;");
  push("  bool compactPresentation;");
  push("  bool expandedPresentation;");
  push("};");
  push("");

  const aliasArrays: string[] = [];
  const routeArrays: string[] = [];
  const stateArrays: string[] = [];

  capabilities.forEach((capability, ordinal) => {
    push(`// --- ${capability.id} (${capability.disposition}) ---`);

    const aliasSymbol = `kAliases_${ordinal}`;
    const routeSymbol = `kRoutes_${ordinal}`;
    const stateSymbol = `kVisibleStates_${ordinal}`;

    if (capability.stockAliases.length > 0) {
      aliasArrays.push(aliasSymbol);
      push(
        `inline constexpr StockAlias ${aliasSymbol}[] = {${capability.stockAliases
          .map((alias) => `{${cString(alias)}}`)
          .join(", ")}};`,
      );
    }
    const routes = capability.plampyRecipe ? capability.plampyRecipe.packages : [];
    if (routes.length > 0) {
      routeArrays.push(routeSymbol);
      push(
        `inline constexpr PackageRoute ${routeSymbol}[] = {${routes
          .map((route) => `{${cString(route.packageName)}, ${cString(route.bundleDir)}}`)
          .join(", ")}};`,
      );
    }
    stateArrays.push(stateSymbol);
    push(
      `inline constexpr const char *${stateSymbol}[] = {${capability.deviceVector.visibleStates
        .map((state) => cString(state))
        .join(", ")}};`,
    );
    push("");
  });

  push("// Constant-time lookup by typed CapabilityId is the array position: kCapabilities[ordinal].");
  push("// kTagIndex mirrors the precomputed tag order for cross-TU identity checks.");
  push("inline constexpr CapabilityEntry kCapabilities[kCapabilityCount] = {");
  capabilities.forEach((capability, ordinal) => {
    const active = input.selectedStage.activeCapabilities.includes(capability.id);
    const aliasRef = capability.stockAliases.length > 0 ? `kAliases_${ordinal}` : "nullptr";
    const routeRef = (capability.plampyRecipe?.packages.length ?? 0) > 0 ? `kRoutes_${ordinal}` : "nullptr";
    const stateRef = `kVisibleStates_${ordinal}`;
    push(
      `  {CapabilityId::${capabilityEnumerator(capability.id)}, ModuleId::${capability.module}, ` +
        `${cString(capability.id)}, EvidenceDisposition::${dispositionEnumerator(capability.disposition)}, ` +
        `${capability.rendererFamily ? cString(capability.rendererFamily) : "nullptr"}, ` +
        `${capability.lifecycleEvidence ? cString(capability.lifecycleEvidence) : "nullptr"}, ` +
        `${hex32(fnv1a32(capability.id))}, ${hex32(active ? 1 << ordinal : 0)}, ` +
        `${capability.disposition === "eligible" ? "true" : "false"}, ` +
        `${aliasRef}, ${capability.stockAliases.length}, ` +
        `${routeRef}, ${capability.plampyRecipe?.packages.length ?? 0}, ` +
        `${stateRef}, ${capability.deviceVector.visibleStates.length}, ` +
        `${capability.deviceVector.presentations.includes("compact") ? "true" : "false"}, ` +
        `${capability.deviceVector.presentations.includes("expanded") ? "true" : "false"}},`,
    );
  });
  push("};");
  push("");
  push("// Precomputed tag index (sorted by tag) for constant-time tag -> capability lookup.");
  push("inline constexpr CapabilityId kTagIndex[kCapabilityCount] = {");
  const byTag = capabilities
    .map((capability, ordinal) => ({ tag: fnv1a32(capability.id), ordinal }))
    .sort((left, right) => left.tag - right.tag);
  byTag.forEach(({ ordinal }) => {
    push(`  CapabilityId::${capabilityEnumerator(capabilities[ordinal].id)}, // tag ${hex32(fnv1a32(capabilities[ordinal].id))}`);
  });
  push("};");
  push("");
  push("static_assert(kModuleCount == 30, \"census is closed at 30 module identities\");");
  push("static_assert(kCapabilityCount == 32, \"census is closed at 32 capabilities\");");
  push("static_assert(kEligibleCount == 13, \"accepted 21D50 Plampy map has 13 eligible routes\");");
  push(
    "static_assert(sizeof(kCapabilities) / sizeof(kCapabilities[0]) == kCapabilityCount, \"catalog length mismatch\");",
  );
  push("");
  push("} // namespace generated");
  push("} // namespace plampycc");
  push("");
  push("#endif");

  return `${lines.join("\n")}\n`;
}

function renderJson(
  input: ThemeManifest,
  contract: CensusContract,
  digests: { catalog: string; activationSet: string },
): string {
  const bitset = input.selectedStage.activeCapabilities.reduce(
    (accumulator, id, ordinal) => accumulator | (1 << contract.capabilityIds.indexOf(id)),
    0,
  );
  const payload = {
    schema: "plampycc-theme-catalog/v1",
    generator: "tools/theme-catalog/generate.ts",
    target: contract.target,
    seed: {
      file: input.seed.file,
      sha256: input.seed.sha256,
      sourceSha256: input.seed.sourceSha256,
    },
    counts: {
      modules: contract.moduleIds.length,
      capabilities: contract.capabilityIds.length,
      eligible: contract.eligibleIds.length,
      stockOnly: contract.capabilityIds.length - contract.eligibleIds.length,
    },
    selectedStage: input.selectedStage,
    activationBitset: `0x${bitset.toString(16).padStart(4, "0")}`,
    catalogDigest: `sha256:${digests.catalog}`,
    activationSetDigest: `sha256:${digests.activationSet}`,
    stageCardinality: { Q0: 0, A1: 1, A2: 4, A3: contract.eligibleIds.length, R1: contract.eligibleIds.length },
    modules: input.modules.map((module) => ({
      id: module.id,
      safeDefault: module.safeDefault,
      capabilities: module.capabilities,
    })),
    capabilities: input.capabilities.map((capability, ordinal) => ({
      ordinal,
      id: capability.id,
      module: capability.module,
      localIndex: capability.localIndex,
      tag: fnv1a32(capability.id),
      tagHex: hex32(fnv1a32(capability.id)),
      disposition: capability.disposition,
      seedDisposition: capability.seedDisposition,
      rendererFamily: capability.rendererFamily,
      hostForm: capability.hostForm,
      lifecycleEvidence: capability.lifecycleEvidence,
      activationEligible: capability.disposition === "eligible",
      active: input.selectedStage.activeCapabilities.includes(capability.id),
      stockAliases: capability.stockAliases,
      stockAssets: capability.stockAssets,
      aliasDisambiguation: capability.aliasDisambiguation ?? null,
      routes: capability.plampyRecipe?.packages ?? [],
      deviceVector: capability.deviceVector,
    })),
  };
  return `${JSON.stringify(payload, null, 2)}\n`;
}

export type RenderOptions = {
  readonly contract?: CensusContract;
  readonly assetExists?: (path: string) => boolean;
};

export type RenderedCatalog = {
  readonly header: string;
  readonly json: string;
  readonly digests: { readonly catalog: string; readonly activationSet: string };
};

const layoutAssetExists = (path: string): boolean => existsSync(join(REPO_ROOT, path));

export function renderCatalog(
  input: ThemeManifest,
  options: RenderOptions = {},
): RenderedCatalog {
  const contract = options.contract ?? CONTRACT_21D50;
  const assetExists = options.assetExists ?? layoutAssetExists;
  const result = validateManifest(input, { contract, assetExists });
  if (!result.ok) {
    const detail = result.errors.map((error) => `[${error.code}] ${error.message}`).join("\n");
    throw new Error(`theme catalog generation failed:\n${detail}`);
  }
  const digests = computeDigests(input);
  return {
    header: renderHeader(input, contract, digests),
    json: renderJson(input, contract, digests),
    digests,
  };
}

function isCheckMode(args: string[]): boolean {
  return args.includes("--check");
}

function main(): void {
  const check = isCheckMode(process.argv.slice(2));
  let rendered: RenderedCatalog;
  try {
    rendered = renderCatalog(manifest);
  } catch (error) {
    console.error((error as Error).message);
    process.exit(1);
  }

  const counts = {
    modules: manifest.modules.length,
    capabilities: manifest.capabilities.length,
    eligible: CONTRACT_21D50.eligibleIds.length,
    stockOnly: CONTRACT_21D50.capabilityIds.length - CONTRACT_21D50.eligibleIds.length,
  };

  if (check) {
    const existingHeader = existsSync(HEADER_PATH)
      ? readFileSync(HEADER_PATH, "utf8")
      : "";
    const existingJson = existsSync(JSON_PATH) ? readFileSync(JSON_PATH, "utf8") : "";
    const headerOk = existingHeader === rendered.header;
    const jsonOk = existingJson === rendered.json;
    if (headerOk && jsonOk) {
      console.log(
        `PASS: theme catalog regenerated byte-identical (${counts.modules} modules, ${counts.capabilities} capabilities, ${counts.eligible} eligible, ${counts.stockOnly} stock-only); catalog ${rendered.digests.catalog}; activation ${rendered.digests.activationSet}`,
      );
      return;
    }
    console.error(`FAIL: generated theme catalog is stale (${HEADER_PATH} ${headerOk ? "OK" : "STALE"}, ${JSON_PATH} ${jsonOk ? "OK" : "STALE"})`);
    process.exit(1);
  }

  writeFileSync(HEADER_PATH, rendered.header);
  writeFileSync(JSON_PATH, rendered.json);
  console.log(
    `WROTE ${HEADER_PATH} and ${JSON_PATH} (${counts.modules} modules, ${counts.capabilities} capabilities, ${counts.eligible} eligible, ${counts.stockOnly} stock-only); catalog ${rendered.digests.catalog}; activation ${rendered.digests.activationSet}`,
  );
}

if (import.meta.main) {
  main();
}
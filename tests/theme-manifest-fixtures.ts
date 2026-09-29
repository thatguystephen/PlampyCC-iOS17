// Shared typed fixtures for the theme-catalog tests. Mutable, widened mirrors
// of the manifest records so tests can build invalid and extension inputs
// without casting unchecked data to ThemeManifest. No test or helper anywhere
// in the catalog surface uses `as unknown as ThemeManifest`.

import { manifest } from "../manifest/theme-manifest.ts";

export type MutableSelectorEvidence = {
  role: string;
  form: string;
  name: string;
  encoding: string | null;
  callSiteSource: string;
};

export type MutableFactEvidence = {
  fact: string;
  statement: string;
  source: string;
};

export type MutableEvidence = {
  id: string;
  module: string;
  capability: string;
  evidenceKind: string;
  ownerClass: string;
  hostClass: string;
  selectors: MutableSelectorEvidence[];
  facts: MutableFactEvidence[];
};

export type MutableAdapterSeam = {
  name: string;
  ownerClass: string;
  selector: string;
  encoding: string;
  predecessorType: string;
};

export type MutableAdapter = {
  family: string;
  adapter: string;
  seams: MutableAdapterSeam[];
};

export type MutableModule = {
  id: string;
  safeDefault: string;
  seedRendererEvidenceStatus: string;
  capabilities: string[];
};

export type MutableRoute = {
  packageName: string;
  bundleDir: string;
  requiredAsset: string;
};

export type MutableCapability = {
  id: string;
  module: string;
  localIndex: number;
  disposition: string;
  seedDisposition: string;
  seedEvidenceType: string;
  rendererFamily: string | null;
  hostForm: string;
  stockAliases: string[];
  stockAssets: string[];
  aliasDisambiguation?: { alias: string; resolution: string; rationale: string };
  plampyRecipe: { packages: MutableRoute[] } | null;
  lifecycleEvidence: string | null;
  deviceVector: { visibleStates: string[]; presentations: string[] };
};

export type MutableStage = {
  name: string;
  activeCapabilities: string[];
};

export type MutableManifest = {
  schema: string;
  target: { productType: string; productVersion: string; build: string };
  seed: { file: string; sha256: string; sourceSha256: string };
  modules: MutableModule[];
  capabilities: MutableCapability[];
  rendererFamilyAdapters: MutableAdapter[];
  lifecycleEvidenceRecords: Record<string, MutableEvidence>;
  selectedStage: MutableStage;
};

// JSON round-trip yields `any`, which assigns to the typed fixture without a
// cast. The fixture type is a mutable mirror, not ThemeManifest.
export const cloneManifest = (): MutableManifest =>
  JSON.parse(JSON.stringify(manifest));

export const byCapability = (copy: MutableManifest, id: string): MutableCapability => {
  const found = copy.capabilities.find((capability) => capability.id === id);
  if (found === undefined) {
    throw new Error(`fixture capability not found: ${id}`);
  }
  return found;
};

export const byModule = (copy: MutableManifest, id: string): MutableModule => {
  const found = copy.modules.find((module) => module.id === id);
  if (found === undefined) {
    throw new Error(`fixture module not found: ${id}`);
  }
  return found;
};

const sourceFor = (kind: string, what: string): string =>
  kind === "direct-21d50" ? `21D50 ${what}` : `synthetic ${what}`;

// A structurally complete lifecycle evidence record. `direct-21d50` binds every
// source to build 21D50; `synthetic-fixture` binds none and can never activate.
export const buildEvidence = (
  capabilityId: string,
  moduleId: string,
  kind: "direct-21d50" | "synthetic-fixture" = "direct-21d50",
): MutableEvidence => {
  const source = (what: string): string => sourceFor(kind, what);
  return {
    id: `evidence:${capabilityId}`,
    module: moduleId,
    capability: capabilityId,
    evidenceKind: kind,
    ownerClass: moduleId,
    hostClass: `HostOf${moduleId}`,
    selectors: [
      {
        role: "bind",
        form: "selector",
        name: "setGlyphPackageDescription:",
        encoding: "v24@0:8@16",
        callSiteSource: source("bind selector call site"),
      },
      {
        role: "close",
        form: "signal",
        name: "moduleWillDisappear",
        encoding: null,
        callSiteSource: source("close signal call site"),
      },
      {
        role: "detach",
        form: "signal",
        name: "viewWillMoveToWindow:nil",
        encoding: null,
        callSiteSource: source("detach signal call site"),
      },
      {
        role: "reuse",
        form: "selector",
        name: "layoutSubviews",
        encoding: "v@8@0:8",
        callSiteSource: source("reuse selector call site"),
      },
    ],
    facts: [
      {
        fact: "epoch-invalidation",
        statement: "invalidate the session epoch before rebinding",
        source: source("epoch invalidation fact"),
      },
      {
        fact: "producer-tag",
        statement: "tag the stock producer",
        source: source("producer tag fact"),
      },
      {
        fact: "stock-capture",
        statement: "capture the stock representation",
        source: source("stock capture fact"),
      },
      {
        fact: "newer-stock-adoption",
        statement: "adopt a genuinely newer stock value",
        source: source("newer stock adoption fact"),
      },
      {
        fact: "restoration",
        statement: "restore the stock representation once",
        source: source("restoration fact"),
      },
      {
        fact: "teardown",
        statement: "tear down owned state",
        source: source("teardown fact"),
      },
      {
        fact: "missing-fact-fail-open",
        statement: "on a missing fact, forward the exact incoming stock value once",
        source: source("fail-open missing fact"),
      },
    ],
  };
};
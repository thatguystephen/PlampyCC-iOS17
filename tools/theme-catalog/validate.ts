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
//                    capability IDs, malformed module/capability records
//   ownership        capability/module ownership is inconsistent (cross-module
//                    references, local-index gaps, unlisted capabilities,
//                    duplicate capability membership inside or across module
//                    capability lists)
//   disposition      missing/unknown disposition, implicit eligibility default,
//                    stock-only record emitting a route, eligible record without
//                    family/recipe, or a seed-disposition mapping violation
//   alias            empty/duplicate alias set or an alias collision without
//                    explicit disambiguation
//   asset            eligible record without a validated required Plampy asset
//   family           Renderer Family outside the closed 21D50 set, missing or
//                    duplicated adapter declaration, or an adapter/seam
//                    declaration that is not the exact typed CAML declaration
//   evidence         structurally incomplete lifecycle evidence (missing
//                    role/fact, selector without encoding or call-site source,
//                    placeholder-only record, key/record.id mismatch, sources
//                    not bound to 21D50, or synthetic evidence claiming direct
//                    21D50 evidence); dangling references; an eligible
//                    capability in the activation set without complete direct
//                    21D50 lifecycle evidence
//   string           newline/control characters in a manifest string that
//                    generation embeds in C++
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
//
// The validator accepts `unknown` at its external boundary and narrows each
// value by validation before operating on it. It never casts unchecked input
// to ThemeManifest.

import {
  LIFECYCLE_FACTS,
  LIFECYCLE_ROLES,
  type LifecycleFact,
  type LifecycleRole,
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
  | "string"
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
export const STAGE_CARDINALITY: Readonly<Record<string, number | "eligible-set">> = {
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
const SEED_DISPOSITIONS: readonly string[] = [
  "verified_asset_candidate",
  "missing_asset_stock",
  "unknown_renderer_stock",
  "unresolved_catalog_stock",
];
const SEED_EVIDENCE_TYPES: readonly string[] = ["animated_caml", "static_png", "unknown"];
const MODULE_RENDERER_STATUSES: readonly string[] = ["verified", "inferred", "unknown"];
const HOST_FORMS: readonly string[] = [
  "button-host",
  "slider-host",
  "expansion-host",
  "unknown-host",
];

const MODULE_ID_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const CAPABILITY_ID_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

// The 21D50 renderer-family set is closed: CAML Package Setter is the only
// eligible family. Invented family names are rejected even when accompanied by
// arbitrary adapter strings.
export const RENDERER_FAMILIES: readonly string[] = ["caml-package-setter"];

// The exact typed CAML adapter/seam declaration (typed predecessor aliases, not
// raw IMP). A declaration that differs in any field is not this adapter.
export const CAML_ADAPTER_NAME = "CAMLAdapter";
export type CamlSeamDeclaration = {
  readonly name: string;
  readonly ownerClass: string;
  readonly selector: string;
  readonly encoding: string;
  readonly predecessorType: string;
};
export const CAML_SEAMS: readonly CamlSeamDeclaration[] = [
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
];

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

// Newlines and control characters must never reach a C++ string literal.
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
// Placeholder-only evidence values prove nothing.
const PLACEHOLDER_VALUE = /^(todo|tbd|tba|placeholder|synthetic|none|n\/a|na|xxx|\?|-|\.\.\.)$/i;

const isPlaceholder = (value: string): boolean => PLACEHOLDER_VALUE.test(value.trim());
const isBoundTo21D50 = (value: string): boolean => value.includes("21D50");

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

type Fail = (code: ValidationCode, message: string) => void;

// ---- Objective-C method-encoding validation (ABI evidence shape) ----------
//
// A method encoding is the arm64 method_getTypeEncoding form:
//
//   <return-type><argument-frame-size><argument-slot>+
//   argument-slot := <type><offset>
//
// e.g. v24@0:8@16 (void return; 24-byte argument frame; self id @0,
// _cmd SEL @8, one id argument @16). A bare scalar or object token ("i",
// "q", "@\"NSString\"") is not a method signature and never proves selector
// ABI.
//
// For the exact lifecycle evidence schema the expected message shape is the
// typed predecessor-alias shape the typed evidence records declare
// ("void (*)(id, SEL, id)"): the return ABI is void (v), self is id (@0),
// _cmd is SEL (:8), and every explicit argument is an object (id) in the next
// 8-byte slot. The typed evidence record's selector name declares the
// argument shape — one explicit argument per colon — so the encoding's
// explicit argument count must equal the selector's colon count. A wrong
// return ABI (including structurally valid categories such as i, q, @, B,
// ^v) conflicts with the typed void predecessor contract and fails, as do
// missing self/_cmd positions, selector/encoding arity mismatches, truncated
// or offset/frame-inconsistent encodings, and plausible-but-wrong explicit
// argument types (# Class, * char *, : SEL, @? block, scalars, pointers,
// structs).
//
// Parser acceptance is static ABI-shape evidence only. It does NOT prove the
// runtime ABI: that requires device-side method-signature verification (M1,
// out of M0 scope). Direct 21D50 source binding and the typed selector/signal
// evidence requirements are unchanged.

type ParsedType = { readonly text: string; readonly next: number };
type ParsedNumber = { readonly value: number; readonly next: number };

const TYPE_QUALIFIERS = "rnNoORV";
const SIMPLE_TYPE_CHARS = "vicslqCISLQfdBD#:*?";
// arm64: id, SEL, and every accepted lifecycle argument occupy one 8-byte slot.
const SLOT_SIZE = 8;

function parseDigits(input: string, start: number): ParsedNumber | null {
  let index = start;
  while (index < input.length && input[index]! >= "0" && input[index]! <= "9") index += 1;
  if (index === start) return null;
  return { value: Number(input.slice(start, index)), next: index };
}

function parseObjcType(input: string, start: number): ParsedType | null {
  let index = start;
  while (index < input.length && TYPE_QUALIFIERS.includes(input[index]!)) index += 1;
  if (index >= input.length) return null;
  const typeStart = index;
  const char = input[index]!;
  index += 1;
  if (char === "@") {
    // id, block (@?), or typed object (@"NSString").
    if (input[index] === "?") index += 1;
    else if (input[index] === '"') {
      index += 1;
      const close = input.indexOf('"', index);
      if (close < 0) return null;
      index = close + 1;
    }
  } else if (char === "^") {
    const target = parseObjcType(input, index);
    if (target === null) return null;
    index = target.next;
  } else if (char === "b") {
    const bits = parseDigits(input, index);
    if (bits === null) return null;
    index = bits.next;
  } else if (char === "[") {
    const count = parseDigits(input, index);
    if (count === null) return null;
    index = count.next;
    let elements = 0;
    while (index < input.length && input[index] !== "]") {
      const element = parseObjcType(input, index);
      if (element === null) return null;
      index = element.next;
      elements += 1;
    }
    if (input[index] !== "]" || elements === 0) return null;
    index += 1;
  } else if (char === "(" || char === "{") {
    const close = char === "(" ? ")" : "}";
    while (index < input.length && input[index] !== "=" && input[index] !== close) index += 1;
    if (input[index] === "=") {
      index += 1;
      let members = 0;
      while (index < input.length && input[index] !== close) {
        const member = parseObjcType(input, index);
        if (member === null) return null;
        index = member.next;
        members += 1;
      }
      if (members === 0) return null;
    }
    if (input[index] !== close) return null;
    index += 1;
  } else if (!SIMPLE_TYPE_CHARS.includes(char)) {
    return null;
  }
  return { text: input.slice(typeStart, index), next: index };
}

export type MethodSlot = { readonly type: string; readonly offset: number };
export type MethodEncoding = {
  readonly returnType: string;
  readonly frameSize: number;
  readonly slots: readonly MethodSlot[];
};

// Parse a method encoding; null when the text is not a well-formed method
// signature (scalar/object token, truncated text, dangling type or offset).
export function parseMethodEncoding(encoding: string): MethodEncoding | null {
  const returnType = parseObjcType(encoding, 0);
  if (returnType === null) return null;
  const frameSize = parseDigits(encoding, returnType.next);
  if (frameSize === null) return null;
  let index = frameSize.next;
  const slots: MethodSlot[] = [];
  while (index < encoding.length) {
    const type = parseObjcType(encoding, index);
    if (type === null) return null;
    const offset = parseDigits(encoding, type.next);
    if (offset === null) return null;
    slots.push({ type: type.text, offset: offset.value });
    index = offset.next;
  }
  return { returnType: returnType.text, frameSize: frameSize.value, slots };
}

// Selector grammar: `ident` (zero arguments) or `ident (:ident)* :` (one
// explicit argument per colon). Returns the declared argument count, or null
// when the name is not a well-formed Objective-C selector.
export function selectorArgumentCount(name: string): number | null {
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return 0;
  if (/^[A-Za-z_][A-Za-z0-9_]*(:[A-Za-z_][A-Za-z0-9_]*)*:$/.test(name)) {
    let colons = 0;
    for (const char of name) if (char === ":") colons += 1;
    return colons;
  }
  return null;
}

// Validate one selector encoding against the selector name the typed evidence
// record declares. Lifecycle selector evidence governs the typed void
// predecessor contract ("void (*)(id, SEL, id)"), so the return ABI must be
// void (v): a structurally valid signature with any other return category is
// not acceptable evidence. Returns null when the encoding is valid ABI-shape
// evidence, otherwise the reason it is not.
export function validateSelectorEncoding(
  encoding: string,
  selectorName: string | null,
): string | null {
  const argumentCount = selectorName === null ? null : selectorArgumentCount(selectorName);
  if (selectorName !== null && argumentCount === null) {
    return `selector ${selectorName} is not a well-formed Objective-C selector`;
  }
  const parsed = parseMethodEncoding(encoding);
  if (parsed === null) {
    return (
      `encoding ${encoding} is not a method signature ` +
      `(expected <return><frame-size> then <type><offset> slots for self and _cmd)`
    );
  }
  if (parsed.returnType !== "v") {
    return (
      `encoding ${encoding} return ABI ${parsed.returnType} conflicts with the ` +
      `typed void predecessor contract (expected return type v)`
    );
  }
  const self = parsed.slots[0];
  const cmd = parsed.slots[1];
  if (parsed.slots.length < 2 || self === undefined || self.type !== "@" || self.offset !== 0) {
    return `encoding ${encoding} omits the self position (id @0)`;
  }
  if (cmd === undefined || cmd.type !== ":" || cmd.offset !== 8) {
    return `encoding ${encoding} omits the _cmd position (SEL :8)`;
  }
  for (let slot = 0; slot < parsed.slots.length; slot += 1) {
    if (parsed.slots[slot]!.offset !== slot * SLOT_SIZE) {
      return `encoding ${encoding} has inconsistent argument offsets (truncated or malformed)`;
    }
  }
  if (parsed.frameSize !== parsed.slots.length * SLOT_SIZE) {
    return `encoding ${encoding} has an inconsistent argument frame size (truncated or malformed)`;
  }
  const explicit = parsed.slots.slice(2);
  if (argumentCount !== null && explicit.length !== argumentCount) {
    return (
      `encoding ${encoding} declares ${explicit.length} explicit argument(s) ` +
      `but selector ${String(selectorName)} has ${argumentCount} colon(s)`
    );
  }
  for (let index = 0; index < explicit.length; index += 1) {
    const slot = explicit[index]!;
    if (slot.type !== "@") {
      return (
        `encoding ${encoding} argument ${index + 1} is ${slot.type}, ` +
        `not an object (id) argument`
      );
    }
  }
  return null;
}

// Structural lifecycle-evidence gate. A record is schema-complete only when its
// map key equals record.id; bind, close, detach, and reuse evidence is
// represented exactly once each; every named selector carries a matching
// method encoding and call-site evidence (signals carry call-site evidence and
// no encoding); and every Issue #9 lifecycle fact (epoch invalidation, producer
// tag, stock capture, newer-stock adoption, restoration, teardown, and the
// fail-open missing-fact condition) is present with a non-placeholder statement
// and source. Sources must be explicitly bound to 21D50 exactly when the record
// claims direct-21d50 evidence; synthetic fixtures must not claim it.
export function validateLifecycleEvidenceRecord(
  mapKey: string,
  record: unknown,
  fail: Fail,
): void {
  if (!isObject(record)) {
    fail("evidence", `lifecycle evidence record ${mapKey} is not an object`);
    return;
  }
  const context = `lifecycle evidence ${mapKey}`;
  const id = record.id;
  if (!isString(id) || id.length === 0) {
    fail("evidence", `${context} has a malformed id`);
    return;
  }
  if (id !== mapKey) {
    fail("evidence", `${context} key does not match record.id ${id}`);
  }

  const evidenceKind = record.evidenceKind;
  if (evidenceKind !== "direct-21d50" && evidenceKind !== "synthetic-fixture") {
    fail("evidence", `${context} has an unknown evidence kind: ${String(evidenceKind)}`);
    return;
  }
  const direct = evidenceKind === "direct-21d50";

  for (const field of ["module", "capability", "ownerClass", "hostClass"]) {
    const value = record[field];
    if (!isString(value) || value.length === 0) {
      fail("evidence", `${context} has a malformed ${field}`);
    } else if (isPlaceholder(value)) {
      fail("evidence", `${context} ${field} is placeholder-only`);
    }
  }

  const checkSource = (value: unknown, what: string): void => {
    if (!isString(value) || value.length === 0) {
      fail("evidence", `${context} lacks ${what}`);
      return;
    }
    if (isPlaceholder(value)) {
      fail("evidence", `${context} ${what} is placeholder-only`);
      return;
    }
    if (direct && !isBoundTo21D50(value)) {
      fail("evidence", `${context} ${what} is not explicitly bound to 21D50`);
    }
    if (!direct && isBoundTo21D50(value)) {
      fail("evidence", `synthetic fixture ${mapKey} must not claim direct 21D50 evidence in ${what}`);
    }
  };

  // Selector/signal evidence: exactly one entry per lifecycle role.
  const selectors = record.selectors;
  if (!Array.isArray(selectors)) {
    fail("evidence", `${context} has no selector/signal evidence`);
  } else {
    const roles = new Set<string>();
    for (const raw of selectors as unknown[]) {
      if (!isObject(raw)) {
        fail("evidence", `${context} has a malformed selector/signal entry`);
        continue;
      }
      const role = raw.role;
      if (!isString(role) || !LIFECYCLE_ROLES.includes(role as LifecycleRole)) {
        fail("evidence", `${context} names an unknown lifecycle role: ${String(role)}`);
        continue;
      }
      if (roles.has(role)) {
        fail("evidence", `${context} represents ${role} evidence more than once`);
      }
      roles.add(role);

      const form = raw.form;
      const name = raw.name;
      const nameOk = isString(name) && name.length > 0 && !isPlaceholder(name);
      if (!nameOk) {
        fail("evidence", `${context} ${role} evidence lacks a named selector or signal`);
      }
      if (form === "selector") {
        const encoding = raw.encoding;
        if (!isString(encoding) || encoding.length === 0 || isPlaceholder(encoding)) {
          fail("evidence", `${context} selector ${String(name)} lacks a matching method encoding`);
        } else {
          // ABI-shape evidence: the encoding must be a method signature whose
          // return ABI is void (the typed void predecessor contract) and whose
          // argument shape/types match the selector the typed evidence record
          // declares (self id @0, _cmd SEL :8, one id argument per colon).
          const problem = validateSelectorEncoding(encoding, isString(name) ? name : null);
          if (problem !== null) {
            fail("evidence", `${context} selector ${String(name)} has invalid ABI evidence: ${problem}`);
          }
        }
      } else if (form === "signal") {
        if (raw.encoding !== null) {
          fail("evidence", `${context} signal ${String(name)} must not claim a method encoding`);
        }
      } else {
        fail("evidence", `${context} ${role} evidence has an unknown form: ${String(form)}`);
      }
      checkSource(raw.callSiteSource, `${role} call-site source`);
    }
    for (const role of LIFECYCLE_ROLES) {
      if (!roles.has(role)) {
        fail("evidence", `${context} does not represent ${role} evidence`);
      }
    }
  }

  // Lifecycle fact evidence: exactly one entry per Issue #9 fact.
  const facts = record.facts;
  if (!Array.isArray(facts)) {
    fail("evidence", `${context} has no lifecycle fact evidence`);
  } else {
    const kinds = new Set<string>();
    for (const raw of facts as unknown[]) {
      if (!isObject(raw)) {
        fail("evidence", `${context} has a malformed lifecycle fact entry`);
        continue;
      }
      const fact = raw.fact;
      if (!isString(fact) || !LIFECYCLE_FACTS.includes(fact as LifecycleFact)) {
        fail("evidence", `${context} names an unknown lifecycle fact: ${String(fact)}`);
        continue;
      }
      if (kinds.has(fact)) {
        fail("evidence", `${context} represents ${fact} more than once`);
      }
      kinds.add(fact);
      const statement = raw.statement;
      if (!isString(statement) || statement.length === 0) {
        fail("evidence", `${context} ${fact} lacks a statement`);
      } else if (isPlaceholder(statement)) {
        fail("evidence", `${context} ${fact} statement is placeholder-only`);
      }
      checkSource(raw.source, `${fact} source`);
    }
    for (const fact of LIFECYCLE_FACTS) {
      if (!kinds.has(fact)) {
        fail("evidence", `${context} does not represent the ${fact} fact`);
      }
    }
  }
}

// A record closes activation only when it is structurally complete direct
// 21D50 evidence. Synthetic fixtures prove schema shape and never activate.
export function isDirectLifecycleEvidence(record: unknown): boolean {
  if (!isObject(record)) return false;
  if (record.evidenceKind !== "direct-21d50") return false;
  const sources: unknown[] = [];
  if (Array.isArray(record.selectors)) {
    for (const raw of record.selectors as unknown[]) {
      if (isObject(raw)) sources.push(raw.callSiteSource);
    }
  }
  if (Array.isArray(record.facts)) {
    for (const raw of record.facts as unknown[]) {
      if (isObject(raw)) sources.push(raw.source);
    }
  }
  return (
    sources.length > 0 &&
    sources.every(
      (source) =>
        isString(source) &&
        source.length > 0 &&
        !isPlaceholder(source) &&
        isBoundTo21D50(source),
    )
  );
}

export function validateManifest(
  input: unknown,
  options: ValidateOptions = {},
): ValidationResult {
  const contract = options.contract ?? CONTRACT_21D50;
  const assetExists = options.assetExists ?? (() => true);
  const errors: ValidationIssue[] = [];
  const fail: Fail = (code, message) => {
    errors.push({ code, message });
  };

  if (!isObject(input)) {
    fail("id", "manifest is not an object");
    return { ok: false, errors };
  }
  // Narrowed by the isObject guard above; every field below is re-checked.
  const manifest = input;

  // Embedded C++ string literals may contain no newline/control characters.
  const clean = (value: unknown, what: string): value is string => {
    if (!isString(value) || value.length === 0) return false;
    if (CONTROL_CHARS.test(value)) {
      fail("string", `${what} contains newline/control characters`);
      return false;
    }
    return true;
  };

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

  // ---- record collections -----------------------------------------------------
  const modules: unknown[] = Array.isArray(manifest.modules) ? manifest.modules : [];
  const capabilities: unknown[] = Array.isArray(manifest.capabilities)
    ? manifest.capabilities
    : [];
  const adapters: unknown[] = Array.isArray(manifest.rendererFamilyAdapters)
    ? manifest.rendererFamilyAdapters
    : [];
  const evidenceRecords: unknown = isObject(manifest.lifecycleEvidenceRecords)
    ? manifest.lifecycleEvidenceRecords
    : {};
  const evidenceMap: Mutable = isObject(evidenceRecords) ? evidenceRecords : {};

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

  // ---- module records (identity, safe default, explicit ownership membership) --
  const moduleOwnerships = new Map<string, string[]>();
  for (const entry of modules) {
    if (!isObject(entry)) {
      fail("id", "module record is not an object");
      continue;
    }
    const moduleId = isString(entry.id) ? entry.id : "";
    if (entry.safeDefault !== "stock") {
      fail("id", `module ${moduleId} does not preserve the stock safe default`);
    }
    const rendererStatus = entry.seedRendererEvidenceStatus;
    if (!isString(rendererStatus) || !MODULE_RENDERER_STATUSES.includes(rendererStatus)) {
      fail("id", `module ${moduleId} has a missing or unknown seed renderer evidence status`);
    }
    const members = entry.capabilities;
    if (!Array.isArray(members)) {
      fail("ownership", `module ${moduleId} has a malformed capability list`);
      continue;
    }
    const seen = new Set<string>();
    for (const rawMember of members as unknown[]) {
      if (!clean(rawMember, `module ${moduleId} capability membership`)) {
        fail("ownership", `module ${moduleId} has a malformed capability membership`);
        continue;
      }
      const member = rawMember;
      if (!expectedCapabilities.has(member)) {
        fail("id", `module ${moduleId} lists capability unknown to the census: ${member}`);
      }
      if (seen.has(member)) {
        fail(
          "ownership",
          `module ${moduleId} lists capability ${member} more than once (duplicate ownership membership)`,
        );
        continue;
      }
      seen.add(member);
      const owners = moduleOwnerships.get(member) ?? [];
      owners.push(moduleId);
      moduleOwnerships.set(member, owners);
    }
  }
  // Every capability record appears in exactly one module capability list.
  for (const capabilityId of new Set(capabilityIds)) {
    if (!capabilityId) continue;
    const owners = moduleOwnerships.get(capabilityId) ?? [];
    if (owners.length === 0) {
      fail("ownership", `capability ${capabilityId} is listed by no Module record`);
    } else if (owners.length > 1) {
      fail(
        "ownership",
        `capability ${capabilityId} is listed by ${owners.length} Module records (must appear exactly once)`,
      );
    }
  }

  // ---- adapters (closed Renderer Family set, exact typed CAML declaration) ----
  const adapterFamilies = new Map<string, Mutable>();
  for (const adapter of adapters) {
    if (!isObject(adapter) || !isString(adapter.family)) {
      fail("family", "malformed Renderer Family adapter declaration");
      continue;
    }
    const family = adapter.family;
    if (!RENDERER_FAMILIES.includes(family)) {
      fail("family", `invented Renderer Family adapter declaration: ${family}`);
      continue;
    }
    if (adapterFamilies.has(family)) {
      fail("family", `duplicate Renderer Family adapter declaration: ${family}`);
      continue;
    }
    adapterFamilies.set(family, adapter);

    // The exact typed CAML adapter/seam declaration.
    if (adapter.adapter !== CAML_ADAPTER_NAME) {
      fail(
        "family",
        `Renderer Family ${family} must declare the typed adapter ${CAML_ADAPTER_NAME} (found ${String(adapter.adapter)})`,
      );
    }
    const seams: unknown[] = Array.isArray(adapter.seams) ? adapter.seams : [];
    const seamByName = new Map<string, Mutable>();
    for (const seam of seams) {
      if (!isObject(seam) || !isString(seam.name) || seam.name.length === 0) {
        fail("family", `Renderer Family ${family} has an untyped seam declaration`);
        continue;
      }
      if (seamByName.has(seam.name)) {
        fail("family", `Renderer Family ${family} declares seam ${seam.name} more than once`);
        continue;
      }
      seamByName.set(seam.name, seam);
    }
    if (seamByName.size !== CAML_SEAMS.length) {
      fail(
        "family",
        `Renderer Family ${family} must declare exactly the ${CAML_SEAMS.length} typed CAML seams (found ${seamByName.size})`,
      );
    }
    for (const expected of CAML_SEAMS) {
      const seam = seamByName.get(expected.name);
      if (!seam) {
        fail("family", `Renderer Family ${family} is missing the ${expected.name} seam declaration`);
        continue;
      }
      if (
        seam.ownerClass !== expected.ownerClass ||
        seam.selector !== expected.selector ||
        seam.encoding !== expected.encoding ||
        seam.predecessorType !== expected.predecessorType
      ) {
        fail(
          "family",
          `Renderer Family ${family} seam ${expected.name} is not the exact typed declaration (${expected.ownerClass} ${expected.selector} ${expected.encoding} ${expected.predecessorType})`,
        );
      }
    }
    if (adapters.length !== RENDERER_FAMILIES.length) {
      fail(
        "family",
        `the 21D50 renderer-family set is closed at ${RENDERER_FAMILIES.join(", ")} (found ${adapters.length} adapter declarations)`,
      );
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
    if (!isString(seedDisposition) || !SEED_DISPOSITIONS.includes(seedDisposition)) {
      fail("disposition", `capability ${capabilityId} has a missing or unknown seed disposition`);
      continue;
    }
    const seedEvidenceType = capability.seedEvidenceType;
    if (!isString(seedEvidenceType) || !SEED_EVIDENCE_TYPES.includes(seedEvidenceType)) {
      fail("disposition", `capability ${capabilityId} has a missing or unknown seed evidence type`);
      continue;
    }
    const hostForm = capability.hostForm;
    if (!isString(hostForm) || !HOST_FORMS.includes(hostForm)) {
      fail("id", `capability ${capabilityId} has a missing or unknown host form`);
    }

    // Ownership: module back-reference and contiguous local index.
    const owningModuleEntry = modules.find(
      (moduleEntry) =>
        isObject(moduleEntry) &&
        Array.isArray(moduleEntry.capabilities) &&
        (moduleEntry.capabilities as unknown[]).includes(capabilityId),
    );
    const owningMembers: unknown = isObject(owningModuleEntry)
      ? owningModuleEntry.capabilities
      : undefined;
    if (
      !isObject(owningModuleEntry) ||
      owningModuleEntry.id !== capability.module ||
      !Array.isArray(owningMembers)
    ) {
      fail(
        "ownership",
        `capability ${capabilityId} references Module Identity ${String(capability.module)} that does not own it`,
      );
    } else {
      const index = (owningMembers as unknown[]).indexOf(capabilityId);
      if (capability.localIndex !== index) {
        fail(
          "ownership",
          `capability ${capabilityId} localIndex ${String(capability.localIndex)} does not match its module position ${index}`,
        );
      }
    }

    // Seed disposition mapping must hold exactly.
    const moduleStatus = isObject(owningModuleEntry)
      ? String(owningModuleEntry.seedRendererEvidenceStatus)
      : "";
    const mapped = expectedDisposition(seedDisposition, seedEvidenceType, moduleStatus);
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
    if (!Array.isArray(aliases) || !aliases.every((alias) => isString(alias))) {
      fail("alias", `capability ${capabilityId} has a malformed alias set`);
    } else {
      const aliasList = aliases as string[];
      if (new Set(aliasList).size !== aliasList.length) {
        fail("alias", `capability ${capabilityId} has duplicate aliases`);
      }
      for (const alias of aliasList) {
        if (!clean(alias, `capability ${capabilityId} alias`)) {
          fail("alias", `capability ${capabilityId} has an empty alias`);
        }
        const owners = aliasOwners.get(alias) ?? [];
        owners.push(capability);
        aliasOwners.set(alias, owners);
      }
    }
    const stockAssets = capability.stockAssets;
    if (!Array.isArray(stockAssets)) {
      fail("id", `capability ${capabilityId} has a malformed stock asset list`);
    } else {
      for (const asset of stockAssets as unknown[]) {
        if (!clean(asset, `capability ${capabilityId} stock asset`)) {
          fail("id", `capability ${capabilityId} has a malformed stock asset entry`);
        }
      }
    }
    const deviceVector = capability.deviceVector;
    const visibleStates: unknown = isObject(deviceVector) ? deviceVector.visibleStates : undefined;
    const presentations: unknown = isObject(deviceVector) ? deviceVector.presentations : undefined;
    if (
      !isObject(deviceVector) ||
      !Array.isArray(visibleStates) ||
      visibleStates.length === 0 ||
      !(visibleStates as unknown[]).every((state) => clean(state, `capability ${capabilityId} visible state`)) ||
      !Array.isArray(presentations) ||
      presentations.length === 0 ||
      !(presentations as unknown[]).every(
        (presentation) => presentation === "compact" || presentation === "expanded",
      )
    ) {
      fail("id", `capability ${capabilityId} has a malformed device test vector`);
    }

    // Renderer Family: closed set. Only an eligible record may name a family.
    const family = capability.rendererFamily;
    if (family !== null && family !== undefined) {
      if (!isString(family) || !RENDERER_FAMILIES.includes(family)) {
        fail("family", `capability ${capabilityId} names invented Renderer Family ${String(family)}`);
      }
    }

    // Eligibility: explicit, never defaulted. Eligible records need a verified
    // Renderer Family, a route, and validated assets; stock-only records emit
    // nothing.
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
      for (const route of recipe.packages as unknown[]) {
        if (
          !isObject(route) ||
          !clean(route.packageName, `eligible capability ${capabilityId} route package`) ||
          !clean(route.bundleDir, `eligible capability ${capabilityId} route bundle dir`)
        ) {
          fail("disposition", `eligible capability ${capabilityId} emits a malformed route`);
          continue;
        }
        if (
          Array.isArray(aliases) &&
          aliases.every((alias) => isString(alias)) &&
          !(aliases as string[]).includes(route.packageName)
        ) {
          fail("alias", `route package ${String(route.packageName)} is not a declared alias of ${capabilityId}`);
        }
        const expectedAsset = `layout/Library/Application Support/PlampyCC/Plampy/Assets/${String(route.bundleDir)}/${String(route.packageName)}.ca/main.caml`;
        if (route.requiredAsset !== expectedAsset) {
          fail(
            "asset",
            `eligible capability ${capabilityId} required asset must be ${expectedAsset}`,
          );
        } else if (!assetExists(expectedAsset)) {
          fail("asset", `eligible capability ${capabilityId} required asset is missing: ${expectedAsset}`);
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
  for (const [evidenceId, record] of Object.entries(evidenceMap)) {
    validateLifecycleEvidenceRecord(evidenceId, record, fail);
  }
  for (const entry of capabilities) {
    if (!isObject(entry)) continue;
    const reference = entry.lifecycleEvidence;
    if (reference === null || reference === undefined) continue;
    const capabilityId = String(entry.id);
    if (!isString(reference) || !isObject(evidenceMap[reference])) {
      fail("evidence", `capability ${capabilityId} references dangling lifecycle evidence ${String(reference)}`);
      continue;
    }
    const record = evidenceMap[reference];
    if (!isObject(record)) continue;
    if (record.capability !== entry.id || record.module !== entry.module) {
      fail("evidence", `lifecycle evidence ${reference} does not own capability ${capabilityId}`);
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

  const cardinality = STAGE_CARDINALITY[stageName];
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
    fail("stage-shape", `${stageName} must contain exactly the ${contract.eligibleIds.length} eligible capabilities`);
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
    const evidence = isString(reference) ? evidenceMap[reference] : undefined;
    if (!isDirectLifecycleEvidence(evidence)) {
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

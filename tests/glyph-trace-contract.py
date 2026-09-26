from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Never

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Tweak.xm").read_text()
DIAG = (ROOT / "src/CAMLDiagnostic.xm").read_text()
CORE = (ROOT / "src/CAMLDiagnosticCore.hpp").read_text()
HEADER = (ROOT / "src/CAMLDiagnostic.h").read_text()
WORKFLOW = (ROOT / ".github/workflows/build-rootless.yml").read_text()


def fail(message: str) -> Never:
    raise SystemExit(message)


def assert_true(value: bool, message: str) -> None:
    if not value:
        fail(message)

def function_body(text: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*\(", text)
    if not match:
        fail(f"missing function {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    fail(f"unterminated function {name}")


def allowlist(name: str) -> list[str]:
    match = re.search(rf"{name}\[\]\s*=\s*\{{(.*?)\}}", CORE, re.S)
    if not match:
        fail(f"missing allowlist {name}")
    return re.findall(r'"([^"]+)"', match.group(1))


# Decision-table model of the reconciler. Each ranked cause from
# docs/FLASHLIGHT-DIAGNOSTIC.md must map to exactly one outcome
# token, so one flushed trace separates the causes without free-form text.
def classify(*, enabled: bool, theme_image: bool, glyph_api: bool,
             glyph_slot: bool, icon_mapped: bool, applied: bool,
             supported_selected: bool, stable: bool | None = None,
             identifier_changed: bool = False) -> str:
    if stable is not None:
        return "stable-kept" if stable else "stable-repl"
    if not enabled:
        return "skip-disable"
    if not glyph_api:
        return "skip-no-api"
    if not theme_image:
        return "skip-no-img"
    if not glyph_slot:
        return "skip-id-nil" if identifier_changed else "skip-nil"
    if applied:
        return "glyph-sel-ap" if supported_selected else "glyph-appl"
    if not icon_mapped:
        return "skip-no-icon"
    return "generic-app"


ranked_causes = {
    "hook-admission-or-branch-miss": classify(enabled=True, theme_image=True,
                                              glyph_api=True, glyph_slot=True,
                                              icon_mapped=False, applied=False,
                                              supported_selected=False),
    "theme-image-missing": classify(enabled=True, theme_image=False,
                                    glyph_api=True, glyph_slot=True,
                                    icon_mapped=True, applied=False,
                                    supported_selected=False),
    "glyph-api-missing": classify(enabled=True, theme_image=True,
                                  glyph_api=False, glyph_slot=True,
                                  icon_mapped=True, applied=False,
                                  supported_selected=False),
    "nil-glyph-at-reconcile": classify(enabled=True, theme_image=True,
                                       glyph_api=True, glyph_slot=False,
                                       icon_mapped=True, applied=False,
                                       supported_selected=False),
    "identifier-change-nil-glyph": classify(enabled=True, theme_image=True,
                                             glyph_api=True, glyph_slot=False,
                                             icon_mapped=True, applied=False,
                                             supported_selected=False,
                                             identifier_changed=True),
    "applied-glyph-slot": classify(enabled=True, theme_image=True,
                                   glyph_api=True, glyph_slot=True,
                                   icon_mapped=True, applied=True,
                                   supported_selected=False),
    "applied-both-slots": classify(enabled=True, theme_image=True,
                                   glyph_api=True, glyph_slot=True,
                                   icon_mapped=True, applied=True,
                                   supported_selected=True),
    "post-reconcile-overwrite": classify(enabled=True, theme_image=True,
                                         glyph_api=True, glyph_slot=True,
                                         icon_mapped=True, applied=True,
                                         supported_selected=False, stable=False),
    "applied-and-stable": classify(enabled=True, theme_image=True,
                                   glyph_api=True, glyph_slot=True,
                                   icon_mapped=True, applied=True,
                                   supported_selected=False, stable=True),
}
assert_true(
    len(set(ranked_causes.values())) == len(ranked_causes),
    "ranked flashlight causes no longer map to distinct outcome tokens",
)
assert_true(
    ranked_causes["hook-admission-or-branch-miss"] == "skip-no-icon",
    "generic-path miss must record skip-no-icon (topology discriminator)",
)
assert_true(
    ranked_causes["identifier-change-nil-glyph"] == "skip-id-nil",
    "the identifier-change nil-glyph bail must record its own observable token",
)

# Privacy contract: every outcome literal the reconciler can emit is an
# approved token and can never carry a path fragment.
states = allowlist("kApprovedStates")
classes = allowlist("kApprovedClasses")
site_labels = {"glyph-recon", "glyph-probe"}  # observer site labels, not outcomes
trace_bodies = "\n".join(function_body(SOURCE, name) for name in
                         ("TraceGlyph", "ScheduleGlyphStabilityCheck",
                          "ReconcileFlashlightView", "ReconcileGlyphView"))
emitted = set(re.findall(r'"([a-z]+(?:-[a-z]+)+)"', trace_bodies)) - site_labels
assert_true(bool(emitted), "no glyph trace outcomes found in the reconciler")
unknown = emitted - set(states)
assert_true(not unknown, f"reconciler emits non-approved outcome tokens: {sorted(unknown)}")
assert_true(
    all("/" not in token for token in emitted),
    "outcome tokens must stay fragment-free",
)
expected_outcomes = {
    "skip-disable", "skip-no-api", "skip-no-img", "skip-nil", "skip-id-nil",
    "skip-no-icon", "glyph-appl", "glyph-sel-ap", "generic-app",
    "stable-kept", "stable-repl", "stable-miss", "stable-gone",
}
assert_true(
    emitted == expected_outcomes,
    f"reconciler outcome token set changed: {sorted(emitted ^ expected_outcomes)}",
)
assert_true(
    set(ranked_causes.values()) <= emitted,
    "a ranked cause maps to a token the reconciler cannot emit",
)

# Wire-accuracy contract: the serialized state field (key "g") is emitted with
# a bounded printf precision, so a token longer than that precision would reach
# events.jsonl as a truncation prefix no operator could match against the docs.
# Allowlist length, token uniqueness, serializer precision, and the policy
# constant must agree: tokens serialize exactly as named, never by truncation.
wire_match = re.search(r'\\"g\\":\\"%\.(\d+)s\\"', DIAG)
site_wire_match = re.search(r'\\"s\\":\\"%\.(\d+)s\\"', DIAG)
constant_match = re.search(r"kStateWirePrecision = (\d+)", CORE)
assert_true(wire_match is not None and site_wire_match is not None,
            "serialized state/site wire precisions are missing from the collector")
assert_true(constant_match is not None,
            "kStateWirePrecision is missing from the policy header")
wire = int(wire_match.group(1))
site_wire = int(site_wire_match.group(1))
assert_true(
    int(constant_match.group(1)) == wire,
    "kStateWirePrecision does not match the serializer's state-field precision",
)
assert_true(
    all(len(token) <= wire for token in states),
    f"approved state tokens exceed the {wire}-character state wire limit: "
    f"{sorted(token for token in states if len(token) > wire)}",
)
assert_true(len(set(states)) == len(states), "approved state tokens are not unique")
assert_true(
    all(len(token) <= wire for token in emitted),
    f"outcome tokens exceed the {wire}-character state wire limit",
)
assert_true(
    all(len(label) <= site_wire for label in site_labels),
    f"glyph trace site labels exceed the {site_wire}-character site wire limit",
)

# Documentation contract: the doc must list every emitted wire value literally
# (an operator greps events.jsonl for the documented name) and must not name
# tokens the trace cannot emit.
DOC_PATH = "docs/FLASHLIGHT-DIAGNOSTIC.md"
DOC = (ROOT / DOC_PATH).read_text()
for token in sorted(emitted | site_labels):
    assert_true(f"`{token}`" in DOC,
                f"wire value missing from {DOC_PATH}: {token}")
documented = set(re.findall(r"`((?:skip|glyph|generic|stable)[a-z-]*)`", DOC))
stale = documented - emitted - site_labels
assert_true(not stale, f"{DOC_PATH} documents tokens the trace cannot emit: {sorted(stale)}")

# Evidence cross-reference contract: the cited source path must exist and be
# committed, not an untracked scratch note.
def committed(path: str) -> bool:
    return subprocess.run(["git", "ls-files", "--error-unmatch", path],
                          cwd=ROOT, capture_output=True).returncode == 0


assert_true((ROOT / DOC_PATH).exists() and committed(DOC_PATH),
            "the glyph trace citation must target a committed, valid source path")
assert_true(SOURCE.count(DOC_PATH) >= 1 and CORE.count(DOC_PATH) >= 1,
            "glyph trace sources must cite the committed diagnostic documentation")
for text in (SOURCE, CORE, DIAG):
    assert_true("evidence/flashlight-compact-glyph-" not in text,
                "glyph trace sources still cite the uncommitted evidence note")

# Topology evidence contract: host and ancestor classes the diagnosis depends
# on must be approved, or the trace collapses them to unknown-class.
for required in ("CCUIFlashlightModuleViewController", "CCUIButtonModuleView",
                 "CCUIRoundButton", "CCUIContentModuleContainerViewController",
                 "CCUIButtonModuleViewController"):
    assert_true(required in classes, f"class {required} missing from kApprovedClasses")

# Instrumentation contract: each bail and each applied path records before
# returning, and the applied path schedules the read-only stability probe.
flashlight = function_body(SOURCE, "ReconcileFlashlightView")
generic = function_body(SOURCE, "ReconcileGlyphView")
trace = function_body(SOURCE, "TraceGlyph")
stability = function_body(SOURCE, "ScheduleGlyphStabilityCheck")
assert_true(
    flashlight.count("TraceGlyph(") >= 3 and generic.count("TraceGlyph(") >= 4,
    "reconciler decision points are not all traced",
)
assert_true(
    flashlight.index("TraceGlyph(") < flashlight.index("ReleaseFlashlightGlyphs(view)"),
    "bail outcomes must be recorded before the override is released",
)
assert_true(
    re.search(r'if \(!current\) \{\s*TraceGlyph\(view, "skip-id-nil"\);\s*return;', generic),
    "the identifier-change nil-glyph bail must record skip-id-nil before returning",
)
assert_true("ScheduleGlyphStabilityCheck(view, unselected)" in flashlight,
            "flashlight apply does not schedule the stability probe")
assert_true("ScheduleGlyphStabilityCheck(view, image)" in generic,
            "generic apply does not schedule the stability probe")

# Watchdog contract: the probe is read-only and never re-enters layout.
for forbidden in ("SetGlyphImage(", "SetSelectedGlyphImage(", "setGlyphImage:",
                  "setSelectedGlyphImage:", "setNeedsLayout"):
    assert_true(forbidden not in stability,
                f"stability probe must not perform {forbidden}")
assert_true("GlyphImage(strongView)" in stability,
            "stability probe must re-read the glyph slot it verified")
assert_true(
    stability.index("CAMLDiagnosticPrimitiveAdmission(false)")
    < stability.index("dispatch_after"),
    "release builds must never schedule the stability probe",
)
assert_true(
    "SameImage(current, expected)" in stability,
    "stability verdict must compare against the applied image identity",
)

# Collector contract: the glyph observer shares admission, dedup, ring bounds,
# and the approved-value gate with the existing CAML observers.
assert_true("ObserveGlyph" in HEADER and "const char *outcome" in HEADER,
            "ObserveGlyph is not declared in the collector header")
glyph_body = function_body(DIAG, "ObserveGlyphBody")
assert_true("RecordEventBody(" in glyph_body and "context->outcome" in glyph_body,
            "glyph observer does not route through the shared record path")
assert_true(
    "caml_diag::CopyApproved(event.state" in DIAG
    and "caml_diag::ValueKind::State" in DIAG,
    "C-string outcomes bypass the approved-value gate",
)
assert_true("CopyAncestorClass(view, event.ancestorClass" in DIAG,
            "records no longer capture the _viewControllerForAncestor class")

assert_true(
    "python3 -B tests/glyph-trace-contract.py" in WORKFLOW,
    "glyph trace regression is not wired into the build gate",
)

# Header-glyph observer contract (docs/FLASHLIGHT-DIAGNOSTIC.md): the single
# bounded observer for -[CCUICustomContentModuleBackgroundViewController
# setHeaderGlyphImage:unscaledSymbolPointSize:] must stay observer-only, keep
# the verified ABI shape, and record only approved tokens.
HOOKS = (ROOT / "src/CAMLDiagnosticHooks.mm").read_text()
assert_true("kDiagnosticSiteCount = 8" in DIAG,
            "the header-glyph site is missing from the site count")
for literal in ('"CCUICustomContentModuleBackgroundViewController"',
                '"setHeaderGlyphImage:unscaledSymbolPointSize:"',
                '"v32@0:8@16d24"', '"header-glyph"'):
    assert_true(literal in DIAG, f"header-glyph site descriptor missing: {literal}")
assert_true('sites[7] = { "CCUICustomContentModuleBackgroundViewController"' in DIAG,
            "the header-glyph site is not the eighth bounded diagnostic site")
hook_body = function_body(HOOKS, "CAMLHeaderGlyphHook")
assert_true(
    'ObserveHeaderGlyph(self, image, pointSize, __builtin_return_address(0), "header-glyph")'
    in hook_body,
    "the header-glyph hook does not record the bounded one-frame caller identity",
)
assert_true(
    hook_body.index("ObserveHeaderGlyph(") < hook_body.index("gOriginalHeaderGlyph"),
    "the header-glyph hook must observe before it forwards the original call",
)
assert_true("(self, cmd, image, pointSize)" in hook_body,
            "the header-glyph hook must forward the unchanged image and point size")
assert_true("CAMLCreateReplacementDescription" not in hook_body
            and "CAMLRecordPackageInstall" not in hook_body,
            "the header-glyph hook must stay observer-only")
assert_true("__builtin_return_address(0)" in HOOKS
            and "%p" not in DIAG,
            "caller identity must be reduced to an approved token, never a raw address")
header_states = {"hdr-stock", "hdr-other", "hdr-nil", "hdr-unclass"}
assert_true(header_states <= set(states),
            f"header-glyph comparison tokens missing from kApprovedStates: "
            f"{sorted(header_states - set(states))}")
for token in sorted(header_states | {"header-glyph"}):
    assert_true(f"`{token}`" in DOC,
                f"wire value missing from {DOC_PATH}: {token}")
for symbol in ("flashlight.off.fill", "flashlight.on.fill"):
    assert_true(symbol in DIAG and symbol in DOC,
                f"stock flashlight symbol {symbol} is not pinned in the classifier and the doc")
callers = allowlist("kApprovedCallers")
assert_true({"FlashlightModule", "ControlCenterUIKit"} <= set(callers),
            "bounded caller allowlist is missing the decisive image names")
assert_true("CallerTokenForImage" in CORE and "kUnknownCaller" in CORE,
            "bounded caller identity has no centralized policy")
assert_true('strcmp(site, "header-glyph") == 0) return "header"' in CORE,
            "the header-glyph construction path is not mapped in the policy header")
assert_true("ValueKind::Caller" in DIAG,
            "caller tokens bypass the approved-value gate")
for required in ("CCUICustomContentModuleBackgroundViewController", "UIImage",
                 "_UIImageSymbolImage"):
    assert_true(required in classes,
                f"class {required} missing from kApprovedClasses")
assert_true(len("header-glyph") <= site_wire,
            "the header-glyph site label exceeds the site wire limit")

# Functional header-hook forwarding contract (docs/FLASHLIGHT-DIAGNOSTIC.md):
# the input-side header-glyph record is the caller's push and cannot show what
# the substitution hook forwarded, so the functional hook records one
# privacy-bounded decision token per invocation: a gated bypass, a themed
# substitution, or a fail-open forward of the caller's image. The fixed token
# is the whole verdict — no path, pointer, or identifier rides with it.
hook_states = {"hdr-bypass", "hdr-subst", "hdr-failop"}
assert_true(hook_states <= set(states),
            f"header-hook decision tokens missing from kApprovedStates: "
            f"{sorted(hook_states - set(states))}")
assert_true(not hook_states & header_states,
            "header-hook decision tokens overlap the input-side comparison tokens")
hook_body = function_body(SOURCE, "headerGlyph")
assert_true('ObserveGlyph(self, decision, "header-hook")' in hook_body,
            "the functional hook does not record its forwarding decision")
assert_true(
    hook_body.index('ObserveGlyph(self, decision, "header-hook")')
    < hook_body.index("orig_headerGlyph(self, cmd, argument, pointSize)"),
    "the forwarding decision must be recorded before the original is invoked",
)
assert_true('const char *decision = "hdr-bypass";' in hook_body,
            "the not-applicable gate default is not a bypass verdict")
assert_true('decision = themed ? "hdr-subst" : "hdr-failop";' in hook_body,
            "substitution and fail-open verdicts are not distinguished at the hook")
assert_true(
    all(token not in hook_body for token in ("hdr-stock", "hdr-other", "hdr-nil", "hdr-unclass")),
    "the functional hook must not emit input-side comparison verdicts",
)
assert_true(all("/" not in token for token in hook_states),
            "decision tokens must stay fragment-free")
assert_true(
    all(len(token) <= wire for token in hook_states),
    f"decision tokens exceed the {wire}-character state wire limit",
)
for token in hook_states | {"header-hook"}:
    assert_true(f"`{token}`" in DOC,
                f"wire value missing from {DOC_PATH}: {token}")
assert_true(len("header-hook") <= site_wire,
            "the header-hook site label exceeds the site wire limit")
assert_true('strcmp(site, "header-hook") == 0) return "header"' in CORE,
            "the header-hook construction path is not mapped in the policy header")
assert_true('ObserveGlyph(self, decision, "header-hook")' in SOURCE
            and "%p" not in SOURCE,
            "the decision record must carry an approved token, never a raw pointer")

print(
    "PASS: ranked flashlight causes map to distinct approved outcome tokens, "
    "tokens serialize untruncated under the wire limit, documented names match "
    "events.jsonl literals, topology classes stay distinguishable, the stability "
    "probe is read-only and gated, and the observer shares the collector's "
    "admission/dedup/privacy path"
)

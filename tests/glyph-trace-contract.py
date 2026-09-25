from __future__ import annotations

import re
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
# evidence/flashlight-compact-glyph-21D50.md must map to exactly one outcome
# token, so one flushed trace separates the causes without free-form text.
def classify(*, enabled: bool, theme_image: bool, glyph_api: bool,
             glyph_slot: bool, icon_mapped: bool, applied: bool,
             supported_selected: bool, stable: bool | None = None) -> str:
    if stable is not None:
        return "stability-kept" if stable else "stability-replaced"
    if not enabled:
        return "skip-disabled"
    if not glyph_api:
        return "skip-no-api"
    if not theme_image:
        return "skip-no-image"
    if not glyph_slot:
        return "skip-nil-glyph"
    if applied:
        return "glyph-selected-applied" if supported_selected else "glyph-applied"
    if not icon_mapped:
        return "skip-no-icon"
    return "generic-applied"


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

# Privacy contract: every outcome literal the reconciler can emit is an
# approved token and can never carry a path fragment.
states = allowlist("kApprovedStates")
classes = allowlist("kApprovedClasses")
emitted = set(re.findall(r'"((?:skip|glyph|generic|stability)[a-z-]*)"', SOURCE))
emitted -= {"glyph-reconcile", "glyph-stability"}  # observer site labels, not outcomes
assert_true(bool(emitted), "no glyph trace outcomes found in the reconciler")
unknown = emitted - set(states)
assert_true(not unknown, f"reconciler emits non-approved outcome tokens: {sorted(unknown)}")
assert_true(
    all("/" not in token and len(token) < 32 for token in emitted),
    "outcome tokens must stay fragment-free and bounded",
)

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
    flashlight.count("TraceGlyph(") >= 3 and generic.count("TraceGlyph(") >= 3,
    "reconciler decision points are not all traced",
)
assert_true(
    flashlight.index("TraceGlyph(") < flashlight.index("ReleaseFlashlightGlyphs(view)"),
    "bail outcomes must be recorded before the override is released",
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

print(
    "PASS: ranked flashlight causes map to distinct approved outcome tokens, "
    "topology classes stay distinguishable, the stability probe is read-only and "
    "gated, and the observer shares the collector's admission/dedup/privacy path"
)

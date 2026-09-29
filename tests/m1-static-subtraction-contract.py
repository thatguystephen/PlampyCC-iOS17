"""M1 static-substitution subtraction contract: absence + stock-preservation gates.

M1 (from accepted M0 base 7f8a314ddf9033504ca7c9b17e86f16b9ccdde36) removes
every PlampyCC-owned static, compact, Flashlight, and header glyph substitution
route before the Unified Theme Engine lands. This host gate proves:

1. no removed substitution IMP, predecessor slot, installer call edge,
   ownership key, cache/registry, static asset load/render helper,
   ancestry/identifier route, delayed probe, compact/header substitution hook,
   or substitution-only trace name remains in production source;
2. no non-CAML hook can replace a module glyph: no glyph-setter write exists
   anywhere in source, and the only remaining hook on the header-glyph
   selector is the observer-only diagnostic seam that forwards the caller's
   arguments unchanged (that shipping diagnostic interceptor is removed
   atomically at M2, not here);
3. overlay wallpaper/presentation hook bodies, predecessor slots, installer
   edges, functional preference publication, and the current CAML route
   (three verified setter seams + construct-and-pass factory) remain;
4. the generated M0 Q0 catalog is byte-identical to the accepted base,
   activation stays empty, and every static/Flashlight catalog capability
   resolves stock-only and remains absent from activation;
5. docs/M1-STATIC-SUBTRACTION-CUTOVER.md states the verified-stock
   installation boundary and that no device action is performed here;
6. this gate is wired into CI and the verify-plampycc Doctor surface, the
   Doctor gate count is accurate, and the obsolete static-substitution gates
   are gone.

Red proof: this contract fails on base 7f8a314 (the removed identifiers are
still present there).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Never

ROOT = Path(__file__).resolve().parents[1]
BASE = "7f8a314ddf9033504ca7c9b17e86f16b9ccdde36"
WORKFLOW = ROOT / ".github/workflows/build-rootless.yml"
DOCTOR = ROOT / ".cursor/skills/verify-plampycc/SKILL.md"
CUTOVER_NOTE = "docs/M1-STATIC-SUBTRACTION-CUTOVER.md"


def fail(message: str) -> Never:
    raise SystemExit(message)


def check(value: bool, message: str) -> None:
    if not value:
        fail(message)


def read(path: str) -> str:
    target = ROOT / path
    check(target.is_file(), f"missing file: {path}")
    return target.read_text()


def production_sources() -> dict[str, str]:
    """Hand-written production sources (the M0 generated tables are separate)."""
    sources: dict[str, str] = {}
    for path in sorted((ROOT / "src").rglob("*")):
        if path.is_file() and "generated" not in path.parts:
            sources[str(path.relative_to(ROOT))] = path.read_text()
    check(bool(sources), "no production source files found under src/")
    return sources


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


SOURCES = production_sources()
TWEAK = read("src/Tweak.xm")
DIAG = read("src/CAMLDiagnostic.xm")
HOOKS = read("src/CAMLDiagnosticHooks.mm")
CORE = read("src/CAMLDiagnosticCore.hpp")
REPLACEMENT = read("src/CAMLReplacement.xm")

# ---------------------------------------------------------------------------
# 1. Absence gates: every removed substitution name, key, selector, and trace
#    token must be gone from production source (red on base 7f8a314).
# ---------------------------------------------------------------------------
REMOVED_IDENTIFIERS = (
    # static/compact/header substitution hooks, bodies, and helpers
    "buttonLayout", "roundMove", "compactSetGlyph", "compactSetSelectedGlyph",
    "CompactGlyphSubstitute", "CompactSubstitutedArgument",
    "headerGlyph", "HeaderGlyphSubstitute",
    # predecessor slots and the compact thread-local recursion flag
    "orig_layout", "orig_roundMove", "orig_compactGlyph", "orig_compactSelected",
    "orig_headerGlyph", "gCompactGlyphForwarding",
    # ABI gates and installers that existed only for these paths
    "HeaderGlyphEncodingMatches", "CompactGlyphEncodingMatches",
    "InstallHeaderGlyphHook", "InstallCompactGlyphHooks",
    # static-image identifier map and PNG decode/render/cache path
    "IconForIdentifier", "IconImage", "SizedGlyphArt", "SizedCompactGlyphArt",
    "gSizedArt", "gIconImages", "kGlyphSourceCanvas",
    # static glyph reconciliation, release, and delayed stability probe
    "ReconcileGlyphView", "ReconcileFlashlightView",
    "ReleaseGlyphOverride", "ReleaseFlashlightGlyphs",
    "ScheduleGlyphStabilityCheck",
    # glyph access helpers (read and write)
    "GlyphImage", "SelectedGlyphImage", "SetGlyphImage", "SetSelectedGlyphImage",
    "SameImage",
    # ancestry/identifier routing
    "AncestorController", "ButtonIdentifier",
    # registries and ownership markers
    "gGlyphViews", "kFlashlightOwnedView",
    # substitution-only trace surface (calls, helper, observer, context)
    "TraceGlyph", "ObserveGlyph", "ObserveGlyphBody", "CAMLGlyphContext",
    # substitution-only optical policy helper
    "FlashlightOpticalPolicy", "flashlight_optical",
)
REMOVED_KEYS = (
    "plampy.glyphOverride", "plampy.flashlightGlyphs",
)
REMOVED_TRACE_TOKENS = (
    "glyph-recon", "glyph-probe", "header-hook",
    "hdr-bypass", "hdr-subst", "hdr-failop",
    "glyph-appl", "glyph-sel-ap", "generic-app",
    "skip-disable", "skip-no-api", "skip-no-img", "skip-nil", "skip-id-nil",
    "skip-no-icon",
    "stable-kept", "stable-repl", "stable-miss", "stable-gone",
)
REMOVED_SELECTORS = (
    "setGlyphImage:", "setSelectedGlyphImage:",
    "layoutSubviews", "didMoveToWindow",
)
REMOVED_ART_NAMES = ("FlashlightOn", "FlashlightOff")


def identifier_present(text: str, name: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text) is not None


for source_name, text in SOURCES.items():
    for name in REMOVED_IDENTIFIERS:
        check(not identifier_present(text, name),
              f"removed identifier {name} remains in {source_name}")
    for key in REMOVED_KEYS:
        check(key not in text, f"removed ownership key {key} remains in {source_name}")
    for token in REMOVED_TRACE_TOKENS:
        check(token not in text, f"removed trace token {token} remains in {source_name}")
    for selector in REMOVED_SELECTORS:
        check(selector not in text,
              f"removed hook selector {selector} remains in {source_name}")
    for name in REMOVED_ART_NAMES:
        check(name not in text, f"removed substitution art name {name} remains in {source_name}")
    check(not identifier_present(text, "glyphImage"),
          f"removed glyph getter selector remains in {source_name}")
    check(not identifier_present(text, "selectedGlyphImage"),
          f"removed glyph getter selector remains in {source_name}")
check(not (ROOT / "src/FlashlightOpticalPolicy.hpp").exists(),
      "substitution-only optical policy header still exists")

# No bracketed redaction placeholder may survive in compiled source: the M1
# candidate shipped one as the wallpaper root call and it did not compile.
# Compiled source is everything the tweak and prefs bundles build (src/ and
# prefs/, including generated tables and headers).
PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9_]{2,}\]")
for directory in ("src", "prefs"):
    for path in sorted((ROOT / directory).rglob("*")):
        if path.is_file() and path.suffix in {".m", ".mm", ".x", ".xm", ".h", ".hpp", ".c", ".cpp"}:
            check(PLACEHOLDER.search(path.read_text(errors="replace")) is None,
                  f"bracketed redaction placeholder remains in compiled source {path.relative_to(ROOT)}")

# ---------------------------------------------------------------------------
# 2. No non-CAML hook can replace a module glyph.
# ---------------------------------------------------------------------------
# No glyph-setter write surface exists anywhere (covers objc_msgSend and
# selector forms together with the setter ABI gates above).
for source_name, text in SOURCES.items():
    check("setGlyphImage" not in text and "setSelectedGlyphImage" not in text,
          f"glyph-setter write surface remains in {source_name}")

# The only remaining hook on the header-glyph selector is the shipping
# diagnostic observer (site 7 of the eight-site table): it must stay
# observer-only and forward the caller's image and point size unchanged.
header_hook = function_body(HOOKS, "CAMLHeaderGlyphHook")
check("ObserveHeaderGlyph(" in header_hook,
      "header-glyph diagnostic seam no longer records its bounded observation")
check("(self, cmd, image, pointSize)" in header_hook,
      "header-glyph diagnostic seam must forward the unchanged image and point size")
check("CAMLCreateReplacementDescription" not in header_hook
      and "CAMLRecordPackageInstall" not in header_hook
      and "UIImage" not in header_hook,
      "header-glyph diagnostic seam must stay observer-only (no substitution)")
check(header_hook.index("ObserveHeaderGlyph(") < header_hook.index("gOriginalHeaderGlyph"),
      "header-glyph diagnostic seam must observe before it forwards")
check('"setHeaderGlyphImage:unscaledSymbolPointSize:"' in DIAG
      and "sites[7]" in DIAG and "kDiagnosticSiteCount = 8" in DIAG,
      "the observer-only header-glyph diagnostic site is no longer the eighth bounded site")

# Every Tweak.xm hook installation is overlay-only (the constructor installs
# no glyph route at all).
constructor = function_body(TWEAK, "init_plampycc")
check(constructor.count("Install(") == 3,
      "the Tweak.xm constructor must install exactly the three overlay hooks")
for install in (
    "Install(overlay, @selector(viewDidLoad), (IMP)overlayLoad, (IMP *)&orig_overlayLoad);",
    "Install(overlay, @selector(presentAnimated:withCompletionHandler:), (IMP)present, (IMP *)&orig_present);",
    "Install(overlay, @selector(dismissAnimated:withCompletionHandler:), (IMP)dismiss, (IMP *)&orig_dismiss);",
):
    check(constructor.count(install) == 1, f"missing or duplicated overlay install edge: {install}")

# ---------------------------------------------------------------------------
# 3. Retained behavior: overlay wallpaper/presentation, prefs, CAML route.
# ---------------------------------------------------------------------------
for name in ("overlayLoad", "present", "dismiss", "ReconcileWallpaper",
             "RemoveWallpaper", "Background", "Animate"):
    check(f"static void {name}" in TWEAK or f"static UIView *{name}" in TWEAK,
          f"retained overlay behavior lost: {name}")
for slot in ("orig_overlayLoad", "orig_present", "orig_dismiss"):
    check(slot in TWEAK, f"overlay predecessor slot {slot} was removed")
for key in ("plampy.wallpaper", "plampy.blur", "plampy.presented"):
    check(key in TWEAK, f"wallpaper/presentation state key {key} was removed")
dismiss_body = function_body(TWEAK, "dismiss")
check("CAMLDiagnosticFlushAtDismiss();" in dismiss_body,
      "diagnostic flush must remain at the overlay dismiss seam while the shipping collector is installed (removed atomically at M2)")
check("ReconcileWallpaper(self); Animate(self, NO);" in dismiss_body,
      "dismiss must still reconcile the wallpaper and animate it out")
prefs_body = function_body(TWEAK, "ReloadPrefs")
for key in ('@"kEnabled"', '@"kWallpaperSwitch"', '@"kBlurEffectSwitch"', '@"kThemeType"'):
    check(key in prefs_body, f"preference publication lost: {key}")
check("ReconcileWallpaper(overlay);\n        CAMLReconcilePackageConsumers();" in prefs_body,
      "preference reloads must reconcile overlays and package consumers together")
check("bool PlampyCCFunctionalEnabled(void)" in TWEAK
      and "int PlampyCCThemeType(void)" in TWEAK,
      "functional preference state is no longer exported to the CAML seam")

# Retained wallpaper resolution: ThemeFile() must iterate the theme asset
# roots (AssetRoots()) and resolve theme-relative files under the theme
# name, and the wallpaper path must stay wallpaper.jpeg through that
# resolver.
theme_file = function_body(TWEAK, "ThemeFile")
check("AssetRoots()" in theme_file,
      "ThemeFile() must iterate the theme asset roots (AssetRoots())")
check("ThemeName()" in theme_file and "relativePath" in theme_file
      and "fileExistsAtPath" in theme_file,
      "ThemeFile() must resolve theme-relative files under each asset root")
check("AssetRoots(void)" in TWEAK,
      "the wallpaper asset-root list definition was removed")
check('ThemeFile(@"wallpaper.jpeg")' in function_body(TWEAK, "ReconcileWallpaper"),
      "retained wallpaper code must resolve wallpaper.jpeg through the theme asset roots")

# CAML route unchanged: three verified setter seams with predecessor slots and
# the construct-and-pass factory boundary.
for site in ('"CCUIButtonModuleView", "setGlyphPackageDescription:"',
             '"CCUIRoundButton", "setGlyphPackageDescription:"',
             '"CCUIBaseSliderView", "setGlyphPackageDescription:"'):
    check(site in DIAG, f"verified CAML setter site missing: {site}")
for hook in ("CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook"):
    body = function_body(HOOKS, hook)
    check("CAMLCreateReplacementDescription(" in body
          and body.count("CAMLReleaseReplacement(replacement)") == 1,
          f"CAML construct-and-pass route broken at {hook}")
check(HOOKS.count("CAMLReleaseReplacement(replacement)") == 3,
      "each package hook must own exactly one post-original release")
check("CAMLCreateReplacementDescription" in REPLACEMENT
      and "CAMLReconcilePackageConsumers" in REPLACEMENT,
      "CAML replacement module boundary was removed (M2 work, not M1)")

# ---------------------------------------------------------------------------
# 4. M0 catalog immutability, empty Q0 activation, stock-only static routes.
# ---------------------------------------------------------------------------
def git(*arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True)
    check(result.returncode == 0, f"git {' '.join(arguments)} failed: {result.stderr}")
    return result.stdout


check(git("diff", "--name-only", BASE, "--",
          "src/generated", "manifest", "tools/theme-catalog").strip() == "",
      "the generated M0 catalog, its manifest inputs, or its generator changed since accepted base 7f8a314")

catalog = json.loads(read("src/generated/PlampyCCThemeCatalog.json"))
check(catalog["selectedStage"] == {"name": "Q0", "activeCapabilities": []},
      "the selected stage is not Q0 with an empty activation set")
check(catalog["activationBitset"] == "0x0000", "activation bitset is not empty")
check(catalog["counts"] == {"modules": 30, "capabilities": 32, "eligible": 13, "stockOnly": 19},
      "M0 catalog cardinality changed")
capabilities = catalog["capabilities"]
check(len(capabilities) == 32, "catalog must contain exactly 32 capability records")
for capability in capabilities:
    check(capability["active"] is False,
          f"capability {capability['id']} is active in the Q0 stage")
    if capability["disposition"].startswith("stock-only"):
        check(capability["rendererFamily"] is None and capability["routes"] == []
              and capability["activationEligible"] is False,
              f"stock-only capability {capability['id']} does not resolve stock-only")
flashlight = [c for c in capabilities if c["id"] == "flashlight"]
check(len(flashlight) == 1 and flashlight[0]["disposition"] == "stock-only-static",
      "the Flashlight capability must resolve stock-only-static")
static_stock = [c for c in capabilities if c["disposition"] == "stock-only-static"]
check(all(c["routes"] == [] and c["active"] is False for c in static_stock),
      "a static catalog capability carries a route or an activation")

# ---------------------------------------------------------------------------
# 5. Restoration/install boundary note.
# ---------------------------------------------------------------------------
note = read(CUTOVER_NOTE)
flat_note = re.sub(r"\s+", " ", note)
check("verified stock SpringBoard state" in flat_note,
      "the cutover note must state installation only from a verified stock SpringBoard state")
check("clean SpringBoard restart" in flat_note and "stock verification" in flat_note,
      "the cutover note must state the separately authorized clean SpringBoard restart + stock verification path")
check("no device action" in flat_note.lower(),
      "the cutover note must state that no device action is performed by this task")
check("migration shim" in flat_note,
      "the cutover note must state that no runtime migration shim is invented")
check(subprocess.run(["git", "ls-files", "--error-unmatch", CUTOVER_NOTE],
                     cwd=ROOT, capture_output=True).returncode == 0,
      "the cutover note must be committed, not scratch")

# ---------------------------------------------------------------------------
# 6. Verification-surface wiring and gate-count accuracy.
# ---------------------------------------------------------------------------
COMMAND = "python3 -B tests/m1-static-subtraction-contract.py"
workflow = read(".github/workflows/build-rootless.yml")
doctor = DOCTOR.read_text()
check(COMMAND in workflow, "the M1 contract is not wired into the CI build gate")
check(COMMAND in doctor, "the M1 contract is not wired into the verify-plampycc Doctor surface")
OBSOLETE = (
    "tests/icon-cache-contract.py",
    "tests/compact-glyph-hook-contract.py",
    "tests/compact_hook_support.py",
    "tests/glyph-trace-contract.py",
    "tests/flashlight-optical-contract.py",
    "tests/flashlight-asset-contract.py",
    "tests/native-flashlight-optical.cpp",
    "tests/measure-flashlight-optics.sh",
)
SKILL_TREE = ROOT / ".cursor/skills/verify-plampycc"
SKILL_TEXT = "\n".join(p.read_text() for p in sorted(SKILL_TREE.rglob("*.md")))
for path in OBSOLETE:
    check(not (ROOT / path).exists(), f"obsolete static-substitution gate still exists: {path}")
    check(path not in workflow and path not in doctor
          and Path(path).name not in SKILL_TEXT,
          f"obsolete static-substitution gate is still wired into a verification surface: {path}")
for p in sorted(SKILL_TREE.rglob("*.md")):
    check(PLACEHOLDER.search(p.read_text()) is None,
          f"bracketed redaction placeholder remains in the verify-plampycc skill tree: {p.relative_to(ROOT)}")
doctor_block = doctor.split("## Doctor", 1)[1].split("## Drive", 1)[0]
gate_lines = [line.strip() for line in doctor_block.splitlines()
              if re.match(r"^(python3|bun|\./node_modules)", line.strip())
              and "bun install --frozen-lockfile" not in line]
check(len(gate_lines) == 15,
      f"the Doctor surface must run exactly fifteen gate commands, found {len(gate_lines)}")
check("fifteen gate commands" in doctor,
      "the Doctor gate-count documentation is not accurate")

print(
    "PASS: M1 static substitution is subtracted (no substitution IMP, slot, install "
    "edge, ownership key, cache/registry, render helper, ancestry/identifier route, "
    "delayed probe, compact/header substitution hook, or substitution trace remains), "
    "no non-CAML hook can replace a module glyph, overlay wallpaper/presentation and "
    "the CAML route keep their hooks and predecessor slots, the M0 Q0 catalog is "
    "byte-identical with empty activation and stock-only static/Flashlight routes, the "
    "verified-stock install boundary is documented, and the M1 gate is wired into CI "
    "and the fifteen-command Doctor surface"
)

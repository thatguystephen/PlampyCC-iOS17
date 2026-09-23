// @ts-nocheck
const root = decodeURIComponent(new URL("..", import.meta.url).pathname);

const fail = (message: string): never => { throw new Error(message); };
const assert = (condition: unknown, message: string) => { if (!condition) fail(message); };
const read = async (path: string) => Bun.file(`${root}/${path}`).text();
const exists = async (path: string) => Bun.file(`${root}/${path}`).exists();
function reconcileWallpaper(state: any, imageAvailable = true): any {
  if (!state.enabled || !state.wallpaper || !imageAvailable) return { ...state, wallAttached: false, blurAttached: false, alpha: 0 };
  return { ...state, wallAttached: true, blurAttached: state.blur, alpha: state.presented ? 1 : 0 };
}
function reconcileGlyph(state: any): any {
  const canCapture = state.currentImage !== null;
  if (!state.enabled || !state.mappedIcon || !state.replacementImage || !canCapture) {
    const restore = state.appliedImage && state.currentImage === state.appliedImage ? state.originalImage : state.currentImage;
    return { ...state, currentImage: restore, originalImage: null, appliedImage: null };
  }
  const original = state.appliedImage && state.currentImage !== state.appliedImage ? state.currentImage : state.originalImage ?? state.currentImage;
  return { ...state, currentImage: state.replacementImage, originalImage: original, appliedImage: state.replacementImage };
}
const disableGlyph = (state: any) => reconcileGlyph({ ...state, enabled: false });
const source = await read("src/Tweak.xm");
const makefile = await read("Makefile");
const prefsMakefile = await read("prefs/Makefile");
const workflow = await read(".github/workflows/build-rootless.yml");
const emitter = await read(".github/workflows/emit-manifest.py");
const provenance = await read("PROVENANCE.md");
const blocker = await read("CAML-ROUTING-BLOCKER.md");
const control = await read("control");
const prefsController = await read("prefs/RootListController.m");
const prefsPlist = await read("prefs/Root.plist");
const sites = await read("src/CAMLDiagnostic.xm");
const hooks = await read("src/CAMLDiagnosticHooks.mm");
const replacement = await read("src/CAMLReplacement.xm");
const core = await read("src/CAMLReplacementCore.hpp");


assert(makefile.includes("ARCHS = arm64 arm64e") && makefile.includes("THEOS_PACKAGE_SCHEME = rootless"), "rootless Make contract missing");
assert(prefsMakefile.includes("PlampyCC_INSTALL_PATH = /Library/PreferenceBundles"), "preference install path is not logical");
assert(!makefile.includes("layout/var/jb") && !prefsMakefile.includes("/var/jb"), "logical layout contains a second rootless prefix");
assert(source.includes("#import <rootless.h>") && source.includes("ROOT_PATH_NS(@\"/var/mobile/Library/Application Support/PlampyCC\")"), "rootless runtime path contract missing");
assert(workflow.includes("THEOS_COMMIT: 5280bd038207e14f8bd76f5417aa2fe641c03228"), "workflow does not pin the reviewed Theos revision");
assert(workflow.includes("runs-on: macos-15") && !workflow.includes("macos-14"), "workflow is not pinned to the Apple Silicon macos-15 runner");
assert(workflow.includes("DEVELOPER_DIR: /Applications/Xcode_16.4.app"), "workflow does not pin the documented Xcode 16.4 path");
for (const record of ["test \"$(uname -m)\" = arm64", "sw_vers", "xcodebuild -version", "xcrun clang --version"]) assert(workflow.includes(record), `Apple Silicon preflight does not record ${record}`);
for (const rule of [
  "THEOS_PACKAGE_INSTALL_PREFIX = /var/jb",
  "#define ROOT_PATH_NS(path) @THEOS_PACKAGE_INSTALL_PREFIX path",
  "_THEOS_SCHEME_STAGE = $(_THEOS_STAGING_TMP)$(THEOS_PACKAGE_INSTALL_PREFIX)",
  "rsync -a \"$(THEOS_LAYOUT_DIR_NAME)/\" \"$(THEOS_STAGING_DIR)\"",
  "$(s" + "hell mv $(i) $(_THEOS_SCHEME_STAGE))",
  "TARGET_STRIP = :",
]) assert(workflow.includes(rule), `workflow does not verify Theos rule: ${rule}`);
assert(workflow.includes("make clean package FINALPACKAGE=1 STRIP=0"), "workflow does not build the exact unstripped release companion");
assert(workflow.includes("dpkg-deb -R \"$source_package\"") && workflow.includes("source_dylib=") && workflow.includes("source_preferences=") && workflow.includes("cp \"$symbol_binary\" \"dist/symbols/$arch/$target\""), "workflow does not collect exact UUID companions");
assert(workflow.includes("strip -x \"$source_binary\"") && workflow.includes("dpkg-deb -b \"$RUNNER_TEMP/plampycc-package\""), "workflow does not strip and repack the exact release binary");
assert(workflow.includes("SHA256SUMS") && workflow.includes("tests/caml-diagnostic-artifact.py dist"), "workflow does not emit and verify artifact checksums");

for (const path of [
  "PlampyCC.plist",
  "layout/Library/MobileSubstrate/DynamicLibraries/PlampyCC.plist",
  "layout/Library/PreferenceLoader/Preferences/PlampyCC.plist",
]) assert(await exists(path), `missing logical staged registration ${path}`);
assert(!(await exists("layout/var/jb")), "staged layout still has a rootless prefix directory");
for (const theme of ["Plampy", "Pulsar"]) assert(await exists(`layout/var/mobile/Library/Application Support/PlampyCC/${theme}/wallpaper.jpeg`), `missing staged ${theme} wallpaper`);

const mapping: Record<string, string> = {
  "com.apple.camera": "Camera",
  "com.apple.calculator": "Calculator",
  "com.apple.BarcodeScanner": "QRCode",
  "com.apple.VoiceMemos": "VoiceMemos",
  "com.apple.Magnifier": "Magnifier",
};
const mappingEntries = new Map([...source.matchAll(/@"(com\.apple\.[A-Za-z0-9.]+)"\s*:\s*@"([A-Za-z0-9]+)"/g)].map((match) => [match[1], match[2]]));
assert(mappingEntries.size === Object.keys(mapping).length, "icon mapping has unexpected or missing identifiers");
for (const [identifier, icon] of Object.entries(mapping)) assert(mappingEntries.get(identifier) === icon, `mapping is not exact: ${identifier} -> ${icon}`);

const expectedOutcomes = {
  Camera: { Plampy: "theme", Pulsar: "plampy-fallback" },
  Calculator: { Plampy: "theme", Pulsar: "plampy-fallback" },
  QRCode: { Plampy: "stock", Pulsar: "stock" },
  VoiceMemos: { Plampy: "stock", Pulsar: "stock" },
  Magnifier: { Plampy: "stock", Pulsar: "stock" },
};
async function iconOutcome(theme: string, icon: string): Promise<string> {
  if (await Bun.file(`${root}/layout/var/mobile/Library/Application Support/PlampyCC/${theme}/Icon/${icon}.png`).exists()) return "theme";
  if (theme === "Pulsar" && await Bun.file(`${root}/layout/var/mobile/Library/Application Support/PlampyCC/Plampy/Icon/${icon}.png`).exists()) return "plampy-fallback";
  return "stock";
}
for (const icon of Object.values(mapping)) for (const theme of ["Plampy", "Pulsar"]) assert(await iconOutcome(theme, icon) === expectedOutcomes[icon][theme], `unexpected ${theme} outcome for ${icon}`);

assert(source.includes("static void ReconcileGlyphView") && source.includes("for (id view in gGlyphViews)"), "live glyph reconciliation is not tracked on preference reload");
assert(source.includes("plampy.glyphOverride") && source.includes("state[@\"identifier\"]") && source.includes("state[@\"original\"]"), "glyph ownership state is not identity-aware");
assert(!source.includes("plampy.originalGlyph") && !source.includes("OBJC_ASSOCIATION_ASSIGN"), "glyph/wallpaper state uses stale non-owned association semantics");
assert(source.includes("if (!current) {\n        ReleaseGlyphOverride(view);"), "missing replacement does not release an owned glyph safely");
assert(source.includes("[blur removeFromSuperview]") && source.includes("objc_setAssociatedObject(self, \"plampy.blur\", nil"), "wallpaper teardown does not release blur state");
assert(source.includes("wall.alpha = [objc_getAssociatedObject(self, \"plampy.presented\") boolValue] ? 1 : 0"), "wallpaper reconciliation does not derive presentation visibility");
assert(source.includes("objc_setAssociatedObject(self, \"plampy.presented\", @YES") && source.includes("@NO"), "presentation state is not tracked");
for (const hook of ["Install(button, @selector(layoutSubviews)", "Install(round, @selector(didMoveToWindow)", "Install(overlay, @selector(viewDidLoad)"]) assert(source.includes(hook), `hook coverage missing ${hook}`);
assert(!source.includes("setGlyphPackageDescription:") && !source.includes("CCUIContinuousSliderView"), "Tweak.xm retains the stale CCUIContinuousSliderView package-setter layer");
assert(!source.includes("orig_buttonPackage") && !source.includes("orig_roundPackage") && !source.includes("orig_sliderPackage"), "pass-through package hooks remain in Tweak.xm");
assert(source.includes("bool PlampyCCFunctionalEnabled(void)") && source.includes("int PlampyCCThemeType(void)"), "functional preference state is not exported to the CAML seam");
for (const site of ['"CCUIButtonModuleView", "setGlyphPackageDescription:"', '"CCUIRoundButton", "setGlyphPackageDescription:"', '"CCUIBaseSliderView", "setGlyphPackageDescription:"']) assert(sites.includes(site), `verified setter site missing: ${site}`);
assert(!sites.includes('"CCUIContinuousSliderView"'), "slider site must move to the verified CCUIBaseSliderView superclass");

// Functional animated CAML: verified construct-and-pass route, fail-open.
assert(replacement.includes("ns_returns_retained") && replacement.includes("CAMLCreateReplacementDescription"), "construct-and-pass factory boundary missing");
assert(replacement.includes("initWithPackageName:name inBundle:bundle") && replacement.includes("CAMLThemeRoot("), "verified initializer route missing");
assert(replacement.includes("ROOT_PATH_NS(@\"/var/mobile/Library/Application Support/PlampyCC\")"), "replacement theme root is not the rooted logical root");
assert(replacement.includes("@catch (...)") && replacement.includes("return replacement;"), "replacement factory lacks guarded +1 handoff");
for (const fn of ["CAMLButtonPackageHook", "CAMLRoundPackageHook", "CAMLSliderPackageHook"]) assert(hooks.includes(fn), `package hook missing ${fn}`);
assert(hooks.includes("CAMLCreateReplacementDescription(self, description, false)") && hooks.includes("CAMLCreateReplacementDescription(self, description, true)"), "construct-and-pass factory calls missing");
assert(hooks.includes("argument = replacement ? replacement : description"), "fail-open original-description fallback missing");
assert(hooks.split("CAMLReleaseReplacement(replacement)").length - 1 === 3, "each package hook must own exactly one post-original release");
assert(!hooks.includes("CAMLReleaseReplacement(description)"), "the borrowed incoming description must not be released");
assert(!hooks.includes("objc_release") && hooks.split("[replacement release]").length - 1 === 1, "the pinned-SDK release form is not the exactly-once MRR message release");

// Live CAML preference reconciliation (SP1): owned/applied recovery state,
// weak consumer lifetimes, main-thread reconcile from the preference reload seam.
assert(replacement.includes("weakObjectsHashTable") && replacement.includes("allObjects"), "package consumers are not tracked weakly for their lifetimes");
for (const key of ['@"identifier"', '@"original"', '@"applied"', '@"appliedTheme"']) assert(replacement.includes(key), `package recovery state is not identity-aware: ${key}`);
assert(replacement.includes("plampy.packageOverride") && replacement.includes("plampy.packageSeam"), "package recovery state is not association-scoped to the consumer");
assert(replacement.includes("caml_replacement::ObserveReconcile") && replacement.includes("caml_replacement::PlanReconcileAction") && core.includes("ClassifyInstall") && core.includes("DecideReconcile"), "package reconcile does not run the production decision policy");
assert(replacement.includes("ReadInstalledDescription(consumer, &probe)") && replacement.includes("glyphPackageDescription"), "factory does not require a verified recovery read-back before taking ownership");
assert(replacement.includes("CAMLInvokeOriginalPackage(seam, consumer"), "reconcile does not apply/restore through the original-IMP slots");
assert(replacement.includes("if (![NSThread isMainThread])"), "package state updates are not main-thread confined");
assert(source.includes("ReconcileWallpaper(overlay);\n        CAMLReconcilePackageConsumers();"), "preference reloads do not reconcile package consumers");
assert(hooks.includes("CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 0)") && hooks.includes("CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 2)"), "package hooks do not record owned/applied recovery state");
assert(!replacement.includes("CAML-REPLACEMENT-IMPLEMENTATION.md") && replacement.includes("CAML-ROUTING-BLOCKER.md"), "replacement module points at stale documentation");
assert(!replacement.includes("valueForKey") && !replacement.includes("setValue"), "the replacement route mutates private description state");
assert(core.includes("BundleDirectoryForPackage") && core.includes("\"timer\", \"TimerModule.bundle\"") && core.includes("themeType == 1"), "routing core missing verified timer/Pulsar skip");
assert(core.includes("\"DisplayModule.bundle\"") && core.includes("\"MediaControls.framework\""), "routing core missing verified slider routes");

// Mapping table and staged payload must agree in both directions.
const tableEntries = [...core.matchAll(/\{"([^"]+)", "([^"]+)"\}/g)].map((match) => ({ name: match[1], bundle: match[2] }));
assert(tableEntries.length >= 20, "replacement mapping table is missing entries");
for (const theme of ["Plampy", "Pulsar"]) {
  for (const entry of tableEntries) {
    if (theme === "Plampy" && entry.name === "HAE_1_x_1") continue; // Pulsar-only package, fails open under Plampy
    assert(await exists(`layout/var/mobile/Library/Application Support/PlampyCC/${theme}/Assets/${entry.bundle}/${entry.name}.ca/main.caml`),
      `mapping target absent from staged payload: ${theme} ${entry.name} -> ${entry.bundle}`);
  }
}
const mappedNames = new Set(tableEntries.map((entry) => entry.name));
for (const file of new Bun.Glob("layout/var/mobile/Library/Application Support/PlampyCC/*/Assets/*/*.ca/main.caml").scanSync({ cwd: root, onlyFiles: true })) {
  const parts = file.split("/");
  const name = parts[parts.length - 2].replace(/\.ca$/, "");
  assert(mappedNames.has(name), `staged animated package has no mapping entry: ${file}`);
}
assert(prefsController.includes("setPreferenceValue") && prefsController.includes("CFNotificationCenterPostNotification") && prefsPlist.includes("kEnabled"), "preference lifecycle coverage missing");
for (const field of ["Package: xyz.cypwn.plampycc", "Architecture: iphoneos-arm64", "Depends:"]) assert(control.includes(field), `package metadata missing ${field}`);

async function validateCamlReferences(caml: string, file: string): Promise<string[]> {
  const references = [...caml.matchAll(/src="([^"]+)"/g)].map((match) => match[1]);
  for (const reference of references) {
    if (!reference.startsWith("/var/jb/var/mobile/Library/Application Support/PlampyCC/")) fail(`invalid CAML prefix in ${file}: ${reference}`);
    if (reference.includes("/var/jb/var/jb/") || reference.includes("/var/jb/var/mobile/var/mobile/")) fail(`repeated CAML prefix in ${file}: ${reference}`);
    const staged = `layout${reference.slice("/var/jb".length)}`;
    if (!await Bun.file(`${root}/${staged}`).exists()) fail(`CAML dependency is absent from logical layout: ${file} -> ${reference}`);
  }
  return references;
}
const camlFiles = [...new Bun.Glob("assets/*/**/*.caml").scanSync({ cwd: root, onlyFiles: true })];
let camlReferenceCount = 0;
for (const file of camlFiles) {
  const caml = await read(file);
  camlReferenceCount += (await validateCamlReferences(caml, file)).length;
  const [, theme, ...assetParts] = file.split("/");
  const mirror = `layout/var/mobile/Library/Application Support/PlampyCC/${theme}/${assetParts.join("/")}`;
  assert(await exists(mirror), `missing staged CAML mirror ${mirror}`);
  assert(await read(mirror) === caml, `source/staged CAML bytes diverge: ${file}`);
}
assert(camlReferenceCount === 81, `expected 81 CAML image references, found ${camlReferenceCount}`);
assert(!source.includes("selectImage") && provenance.includes("pending a Steph product decision") && blocker.includes("Steph must decide"), "selectImage was silently waived or reintroduced");
assert(blocker.includes("construct-and-pass") && blocker.includes("runtime observations"), "CAML implementation status is not explicit in CAML-ROUTING-BLOCKER.md");
assert(provenance.includes("construct-and-pass") && provenance.includes("not runtime-verified"), "CAML implementation status is not explicit in PROVENANCE.md");

const repeatedPrefix = '<contents src="/var/jb/var/jb/var/mobile/Library/Application Support/PlampyCC/Plampy/Icon/Camera.png" />';
let repeatedRejected = false;
try { await validateCamlReferences(repeatedPrefix, "negative-fixture"); } catch { repeatedRejected = true; }
assert(repeatedRejected, "repeated CAML prefixes are accepted by the negative validator");

let wallpaper = reconcileWallpaper({ enabled: true, wallpaper: true, blur: true, presented: true, wallAttached: true, blurAttached: true, alpha: 1 });
wallpaper = reconcileWallpaper({ ...wallpaper, enabled: false });
assert(!wallpaper.wallAttached && !wallpaper.blurAttached && wallpaper.alpha === 0, "disable does not tear down wallpaper and blur together");
wallpaper = reconcileWallpaper({ ...wallpaper, enabled: true });
assert(wallpaper.wallAttached && wallpaper.blurAttached && wallpaper.alpha === 1, "re-enable does not restore blur and visible wallpaper idempotently");
wallpaper = reconcileWallpaper({ ...wallpaper, presented: false });
assert(wallpaper.wallAttached && wallpaper.alpha === 0, "dismissed overlay shows a newly reconciled wallpaper");
wallpaper = reconcileWallpaper({ ...wallpaper, presented: true });
assert(wallpaper.alpha === 1, "presentation before wallpaper creation does not become visible");

let glyph = reconcileGlyph({ enabled: true, identifier: "com.apple.camera", mappedIcon: "Camera", replacementImage: "plampy-camera", currentImage: "stock-camera", originalImage: null, appliedImage: null });
assert(glyph.currentImage === "plampy-camera" && glyph.originalImage === "stock-camera" && glyph.appliedImage === "plampy-camera", "enable does not capture stock ownership before applying a glyph");
glyph = disableGlyph(glyph);
assert(glyph.currentImage === "stock-camera" && glyph.originalImage === null && glyph.appliedImage === null, "disable does not restore and release stock ownership");
glyph = reconcileGlyph({ ...glyph, enabled: true, replacementImage: null });
assert(glyph.currentImage === "stock-camera" && glyph.appliedImage === null, "missing replacement does not preserve stock");
glyph = reconcileGlyph({ enabled: true, identifier: "com.apple.camera", mappedIcon: "Camera", replacementImage: "theme-a", currentImage: "stock-a", originalImage: null, appliedImage: null });
glyph = reconcileGlyph({ ...glyph, replacementImage: "theme-b" });
glyph = disableGlyph(glyph);
assert(glyph.currentImage === "stock-a", "theme change does not restore the captured stock image");
glyph = reconcileGlyph({ enabled: true, identifier: "com.apple.camera", mappedIcon: "Camera", replacementImage: "theme-a", currentImage: "changed-stock", originalImage: "stock-a", appliedImage: "theme-a" });
glyph = disableGlyph(glyph);
assert(glyph.currentImage === "changed-stock", "changed stock image was overwritten during restore");

// SP1-R1/SP1-R2: stateful package recovery transitions are exercised against
// the PRODUCTION transitions (caml_replacement::ClassifyIncoming /
// PlanConstruction / RecordInstall / ObserveReconcile / PlanReconcileAction in
// src/CAMLReplacementCore.hpp, the exact functions the adapter delegates to)
// in tests/native-caml-diagnostic.cpp across all three setter seams, asserting
// object-identity/original preservation (owned re-assignment keeps the real
// stock original, factory misses keep ownership, genuinely newer stock is the
// only adopted original). No TypeScript duplicate of the state model exists
// here: a parallel model cannot establish the adapter's ownership
// transitions, and deleting a string from a Set is not Foundation
// weak-lifetime proof. This file only couples those production transitions to
// the source shapes below.
const nativeTest = await read("tests/native-caml-diagnostic.cpp");
for (const transition of ["ClassifyIncoming", "PlanConstruction", "RecordInstall", "ObserveReconcile", "PlanReconcileAction"]) {
  assert(replacement.includes(`caml_replacement::${transition}(`), `adapter does not delegate to the production transition ${transition}`);
  assert(core.includes(transition), `CAMLReplacementCore.hpp does not define the production transition ${transition}`);
  assert(nativeTest.includes(`${transition}(`), `native tests do not exercise the production transition ${transition}`);
}
assert(nativeTest.includes("TestPackageRecoveryTransitions()"), "stateful recovery transition tests are not wired into the native suite");
for (const seam of ["Seam::ButtonPackage", "Seam::RoundPackage", "Seam::SliderPackage"]) {
  assert(core.includes(seam.replace("Seam::", "")), `recovery policy is missing seam identity ${seam}`);
  assert(nativeTest.includes(seam), `recovery transition coverage is not exercised at ${seam}`);
}
assert(replacement.includes("plampy.packageOwnedReplacement") && replacement.includes("objc_setAssociatedObject(replacement, kPackageOwnedKey") && replacement.includes("ObjCDescriptionOwned"), "constructed replacements are not marked owned for incoming classification");
assert(core.includes("kind == IncomingKind::NewStock") && core.includes("input.prior.original"), "recording does not limit stock adoption to genuinely newer stock");
assert(core.includes("RecoveryState{base.original, nullptr, -1}"), "restoration does not preserve the stock recovery record for stale owned reassignment");
assert(nativeTest.includes("SP1-R3"), "native tests do not cover restore -> stale owned reassignment -> reconcile/re-enable recovery");
assert(replacement.includes("weakObjectsHashTable") && replacement.includes("objc_getAssociatedObject(consumer, kPackageOverrideKey)"), "consumer destruction boundary is not association-scoped records in a weak registry");
assert(nativeTest.includes("weak-lifetime") && nativeTest.includes("not executed on this host"), "native tests overclaim Foundation weak-lifetime proof for consumer destruction");

for (const field of ["target_names", "exactly one package is required", "symbols must contain tweak and preferences targets", "unstrippedBinaries", "sha256"]) assert(emitter.includes(field), `manifest producer contract missing ${field}`);

console.log("PASS: exact mapping outcomes, live glyph ownership, wallpaper/blur transitions, " + camlReferenceCount + " CAML references, verified construct-and-pass CAML route with fail-open fallback and mapping/payload coverage, production-delegated package recovery transitions (identity/original preservation) exercised natively across all three setter seams with honest weak-lifetime limits, rootless staging/strip contract, and producer/consumer manifest coverage");
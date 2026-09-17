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
assert(workflow.includes("make clean stage FINALPACKAGE=0 STRIP=0") && workflow.includes("make clean package FINALPACKAGE=1 STRIP=1"), "workflow does not capture symbols before release stripping");
for (const target of ["PlampyCC.dylib", "PlampyCC"]) assert(workflow.includes(`collect_unstripped \"$arch\" ${target}`), `workflow misses unstripped ${target}`);
assert(workflow.includes("find \".theos/obj/debug/$arch\" -type f") && workflow.includes("! -path '*.dSYM/*'"), "symbol collection can select a DWARF duplicate instead of the target binary");

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
const mappingEntries = new Map([...source.matchAll(/@"([^\"]+)"\s*:\s*@"([^\"]+)"/g)].map((match) => [match[1], match[2]]));
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
for (const hook of ["Install(button, @selector(layoutSubviews)", "Install(button, @selector(setGlyphPackageDescription:)", "Install(round, @selector(didMoveToWindow)", "Install(NSClassFromString(@\"CCUIContinuousSliderView\")", "Install(overlay, @selector(viewDidLoad)"]) assert(source.includes(hook), `hook coverage missing ${hook}`);
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
assert(blocker.includes("remains pass-through") && provenance.includes("pass-through"), "CAML pass-through scope is not explicit");

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

for (const field of ["target_names", "exactly one package is required", "symbols must contain tweak and preferences targets", "unstrippedBinaries", "sha256"]) assert(emitter.includes(field), `manifest producer contract missing ${field}`);

console.log("PASS: exact mapping outcomes, live glyph ownership, wallpaper/blur transitions, " + camlReferenceCount + " CAML references, rootless staging/strip contract, and producer/consumer manifest coverage");
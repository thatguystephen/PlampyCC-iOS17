// @ts-nocheck
const root = new URL("..", import.meta.url).pathname;
const read = async (path: string) => await Bun.file(`${root}/${path}`).text();
const exists = async (path: string) => await Bun.file(`${root}/${path}`).exists();
const source = await read("src/Tweak.xm");
const makefile = await read("Makefile");
const prefs = await read("prefs/RootListController.m");
const workflow = await read(".github/workflows/build-rootless.yml");
const required = [
  ["CCUIButtonModuleView", "layoutSubviews"], ["CCUIButtonModuleView", "setGlyphPackageDescription:"],
  ["CCUIRoundButton", "didMoveToWindow"], ["CCUIRoundButton", "setGlyphPackageDescription:"],
  ["CCUIContinuousSliderView", "setGlyphPackageDescription:"],
  ["CCUIModularControlCenterOverlayViewController", "viewDidLoad"],
  ["CCUIModularControlCenterOverlayViewController", "presentAnimated:withCompletionHandler:"],
  ["CCUIModularControlCenterOverlayViewController", "dismissAnimated:withCompletionHandler:"]
];
for (const [klass, sel] of required) if (!source.includes(klass) || !source.includes(sel)) throw new Error(`missing hook ${klass} ${sel}`);
const legacyPath = ["/var", "mobile", "Documents", ".plampyCC"].join("/");
if (source.includes(legacyPath)) throw new Error("legacy Documents path in production source");
if (!source.includes("ROOT_PATH_NS") || !source.includes("preserve the original glyph")) throw new Error("rootless asset/fallback contract missing");
for (const theme of ["Plampy", "Pulsar"]) {
  if (!await exists(`assets/${theme}/wallpaper.jpeg`)) throw new Error(`missing ${theme} wallpaper`);
  if (!await exists(`layout/var/mobile/Library/Application Support/PlampyCC/${theme}/wallpaper.jpeg`)) throw new Error(`missing staged ${theme} wallpaper`);
  const files = await Array.fromAsync(new Bun.Glob(`assets/${theme}/**/*`).scan({ cwd: root, onlyFiles: true }));
  if (files.length === 0) throw new Error(`missing ${theme} assets`);
}
for (const name of ["Camera", "Calculator"]) {
  if (!await exists(`assets/Plampy/Icon/${name}.png`)) throw new Error(`missing canonical Plampy ${name}`);
  if (!source.includes(`@\"${name}\"`)) throw new Error(`missing ${name} mapping`);
}
if (!source.includes("CAML-ROUTING-BLOCKER.md") && !await exists("CAML-ROUTING-BLOCKER.md")) throw new Error("CAML boundary missing");
if (!source.includes("if (orig_buttonPackage)") || !source.includes("if (orig_roundPackage)")) throw new Error("unsupported CAML fallback missing");
if (!makefile.includes("THEOS_PACKAGE_SCHEME = rootless")) throw new Error("rootless scheme missing");
if (!makefile.includes("PlampyCC_EXTRA_FILES = layout")) throw new Error("rootless payload staging missing");
if (!await exists("control") || !(await read("control")).includes("Package: xyz.cypwn.plampycc")) throw new Error("control metadata missing");
if (!await exists("layout/var/jb/Library/MobileSubstrate/DynamicLibraries/PlampyCC.plist")) throw new Error("staged tweak filter missing");
for (const key of ["loadSpecifiersFromPlistName", "readPreferenceValue", "setPreferenceValue", "CFNotificationCenterPostNotification"]) if (!prefs.includes(key)) throw new Error(`preference lifecycle missing: ${key}`);
if (!await exists("layout/var/jb/Library/PreferenceLoader/Preferences/PlampyCC.plist")) throw new Error("PreferenceLoader registration missing");
for (const artifact of ["dist/", "build-manifest.json", "SHA256SUMS", "unstripped", "source-commit.txt"]) if (!workflow.includes(artifact)) throw new Error(`CI evidence retention missing: ${artifact}`);

// Regression proof: the rejected fixed-point commit must fail the new contract.
const rejected = Bun.spawnSync(["git", "show", "8ea493911bb742eea6de2e6335af44d4bd5a0f2e:Makefile"], { cwd: root }).stdout.toString();
if (rejected.includes("THEOS_PACKAGE_SCHEME = rootless")) throw new Error("rejected candidate unexpectedly satisfies rootless contract");
const rejectedControl = Bun.spawnSync(["git", "cat-file", "-e", "8ea493911bb742eea6de2e6335af44d4bd5a0f2e:control"], { cwd: root });
if (rejectedControl.exitCode === 0) throw new Error("rejected candidate unexpectedly contains package control metadata");
console.log(`PASS: ${required.length} hooks, rootless metadata/filter, both theme payloads/fallbacks, preferences, CAML boundary, CI provenance, and rejected-candidate regression`);

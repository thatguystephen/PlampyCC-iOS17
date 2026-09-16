// @ts-nocheck

const root = new URL("..", import.meta.url).pathname;
const text = async (path: string) => Bun.file(`${root}/${path}`).text();
const exists = async (path: string) => Bun.file(`${root}/${path}`).exists();
const source = await text("src/Tweak.xm");
const makefile = await text("Makefile");
const prefsMakefile = await text("prefs/Makefile");
const workflow = await text(".github/workflows/build-rootless.yml");
const emitter = await text(".github/workflows/emit-manifest.py");
const provenance = await text("PROVENANCE.md");
const blocker = await text("CAML-ROUTING-BLOCKER.md");

const fail = (message: string): never => { throw new Error(message); };
const assert = (condition: unknown, message: string) => { if (!condition) fail(message); };
assert(makefile.includes("ARCHS = arm64 arm64e") && makefile.includes("THEOS_PACKAGE_SCHEME = rootless"), "rootless Make contract missing");
assert(prefsMakefile.includes("PlampyCC_INSTALL_PATH = /Library/PreferenceBundles"), "preference install path must be logical and single-prefixed");
assert(source.includes("#import <rootless.h>") && source.includes("ROOT_PATH_NS(@\"/var/mobile/Library/Application Support/PlampyCC\")"), "actual rootless namespace contract missing");
assert(!source.includes("#define ROOT_PATH_NS"), "identity rootless fallback is forbidden");
assert(provenance.includes("layout/var/jb/var/mobile") && provenance.includes("applies the rootless package prefix once"), "resource contract not documented");
for (const path of [
  "layout/var/jb/Library/MobileSubstrate/DynamicLibraries/PlampyCC.plist",
  "layout/var/jb/Library/PreferenceLoader/Preferences/PlampyCC.plist",
]) assert(await exists(path), `missing staged registration ${path}`);
for (const theme of ["Plampy", "Pulsar"]) {
  assert(await exists(`layout/var/jb/var/mobile/Library/Application Support/PlampyCC/${theme}/wallpaper.jpeg`), `missing staged ${theme} wallpaper`);
  const icons = await Array.fromAsync(new Bun.Glob(`assets/${theme}/Icon/*.png`).scan({ cwd: root, onlyFiles: true }));
  assert(icons.length > 0, `missing ${theme} icon inventory`);
}
const mapping: Record<string, string> = {
  "com.apple.camera": "Camera", "com.apple.calculator": "Calculator",
  "com.apple.BarcodeScanner": "QRCode", "com.apple.VoiceMemos": "VoiceMemos", "com.apple.Magnifier": "Magnifier",
};
for (const [identifier, icon] of Object.entries(mapping)) {
  assert(source.includes(`@\"${identifier}\"`) && source.includes(`@\"${icon}\"`), `mapping missing ${identifier} -> ${icon}`);
  const plampy = await exists(`layout/var/jb/var/mobile/Library/Application Support/PlampyCC/Plampy/Icon/${icon}.png`);
  const pulsar = await exists(`layout/var/jb/var/mobile/Library/Application Support/PlampyCC/Pulsar/Icon/${icon}.png`);
  if (!plampy && !pulsar) assert(source.includes("if (!image && gTheme == 1)"), `${icon} has no installed image or fallback`);
  if (!plampy && pulsar) fail(`${icon} unexpectedly requires unsupported reverse fallback`);
}
assert(source.includes("if (!image && gTheme == 1)") && source.includes("RestoreIcon"), "fallback and preserve-stock transitions missing");
assert(source.includes("NSHashTable weakObjectsHashTable") && source.includes("Install(button") && !source.includes("if (!gEnabled) return"), "hooks are not always installed");
for (const token of ["dispatch_get_main_queue", "ReconcileWallpaper", "RemoveWallpaper", "wall.image = image", "!gEnabled || !gWallpaper", "gBlur && !blur", "!gBlur && blur"]) assert(source.includes(token), `UI reconciliation transition missing: ${token}`);
assert(!source.includes("selectImage"), "selectImage must not be silently reintroduced");
assert(provenance.includes("selectImage") || blocker.includes("selectImage"), "original selectImage disposition undocumented");
assert(blocker.includes("acceptance is therefore BLOCKED") && blocker.includes("rg -n"), "CAML evidence boundary missing");
for (const path of ["dist/packages/", "dist/symbols/arm64", "dist/symbols/arm64e", "SHA256SUMS"]) assert(workflow.includes(path), `CI producer output missing ${path}`);
assert(workflow.includes("python3 .github/workflows/emit-manifest.py"), "CI does not invoke the manifest producer");
assert(emitter.includes("root = Path('dist')") && emitter.includes("(root / 'build-manifest.json').write_text"), "manifest producer does not emit dist/build-manifest.json");
for (const field of ["schemaVersion", "workflowRun", "unstrippedBinaries", "sourceCommit", "GITHUB_REPOSITORY"]) assert(emitter.includes(field), `manifest field missing ${field}`);
const camlFiles = [...new Bun.Glob("assets/*/**/*.caml").scanSync({ cwd: root, onlyFiles: true })];
for (const file of camlFiles) {
  const caml = await text(file);
  for (const match of caml.matchAll(/src="(\/var\/jb\/var\/mobile\/Library\/Application Support\/PlampyCC\/[^"]+)"/g)) {
    const relativePath = match[1].replace("/var/jb/", "layout/var/jb/");
    assert(await exists(relativePath), `CAML resource missing from installed layout: ${file} -> ${match[1]}`);
  }
}
console.log(`PASS: structured rootless paths, ${Object.keys(mapping).length} mappings, fallback/stock transitions, lifecycle reconciliation, CAML dependency inventory, and CI producer contract`);

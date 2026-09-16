// @ts-nocheck
const root = new URL("..", import.meta.url).pathname;
const read = async (path: string) => await Bun.file(`${root}/${path}`).text();
const source = await read("src/Tweak.xm");
const required = [
  ["CCUIButtonModuleView", "layoutSubviews"], ["CCUIButtonModuleView", "setGlyphPackageDescription:"],
  ["CCUIRoundButton", "didMoveToWindow"], ["CCUIRoundButton", "setGlyphPackageDescription:"],
  ["CCUIContinuousSliderView", "setGlyphPackageDescription:"],
  ["CCUIModularControlCenterOverlayViewController", "viewDidLoad"],
  ["CCUIModularControlCenterOverlayViewController", "presentAnimated:withCompletionHandler:"],
  ["CCUIModularControlCenterOverlayViewController", "dismissAnimated:withCompletionHandler:"]
];
for (const [klass, sel] of required) {
  if (!source.includes(klass) || !source.includes(sel)) throw new Error(`missing hook ${klass} ${sel}`);
}
if (source.includes("/var/mobile/Documents/.plampyCC")) throw new Error("legacy Documents path in production source");
for (const theme of ["Plampy", "Pulsar"]) {
  const files = await Array.fromAsync(new Bun.Glob(`assets/${theme}/**/*`).scan({ cwd: root, onlyFiles: true }));
  if (files.length === 0) throw new Error(`missing ${theme} assets`);
}
const makefile = await read("Makefile");
if (!makefile.includes("ARCHS = arm64 arm64e")) throw new Error("rootless architectures missing");
const plist = await read("prefs/Root.plist");
for (const key of ["kEnabled", "kWallpaperSwitch", "kBlurEffectSwitch", "kThemeType", "com.misakaproject.plampyCC"]) if (!plist.includes(key)) throw new Error(`preference ${key} missing`);
console.log(`PASS: ${required.length} hooks, Plampy/Pulsar assets, preferences, rootless arch, and legacy-path guard`);

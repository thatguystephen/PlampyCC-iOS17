// PlampyCC 1.0.2 clean-room reconstruction for iOS 17.3.
//
// M1 — static-substitution subtraction. Every PlampyCC-owned static, compact,
// Flashlight, and header glyph substitution route (hooks, predecessor slots,
// ownership records, caches, registries, ancestry/identifier routing, delayed
// probes, and substitution-only traces) is removed from this file. Flashlight
// and every static/custom glyph path are stock by construction: no hook in the
// shipping dylib can replace a module glyph.
//
// Animated CAML routing runs the verified construct-and-pass route in
// src/CAMLReplacement.xm through the three verified setter seams (installed by
// the diagnostic/CAML site installer in src/CAMLDiagnostic.xm); this file owns
// wallpaper/blur presentation and the functional preference state.
//
// Installation boundary: this artifact may be installed only over a verified
// stock SpringBoard state — see docs/M1-STATIC-SUBTRACTION-CUTOVER.md. There
// is no runtime migration shim: the removed ownership records cannot restore
// live representations.
#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>
#import <CoreFoundation/CoreFoundation.h>
#import <rootless.h>
#import "CAMLDiagnostic.h"
#import "CAMLReplacement.h"
#import "PlampyCCState.h"

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";
static BOOL gEnabled, gWallpaper, gBlur;
static NSInteger gTheme;
static NSHashTable *gOverlays;
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);

static NSString *ThemeName(void) { return gTheme == 1 ? @"Pulsar" : @"Plampy"; }
static NSArray<NSString *> *AssetRoots(void) {
    return @[ ROOT_PATH_NS(@"/Library/Application Support/PlampyCC"),
              ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC") ];
}
static BOOL HasMethod(Class cls, SEL sel) { return cls && class_getInstanceMethod(cls, sel) != NULL; }
static id Call(id obj, SEL sel) { return obj && [obj respondsToSelector:sel] ? ((id(*)(id, SEL))objc_msgSend)(obj, sel) : nil; }

static NSString *ThemeFile(NSString *relativePath) {
    for (NSString *root in [ADDRESS]()) {
        NSString *candidate = [[root stringByAppendingPathComponent:ThemeName()]
            stringByAppendingPathComponent:relativePath];
        if ([[NSFileManager defaultManager] fileExistsAtPath:candidate]) return candidate;
    }
    return nil;
}

static UIView *Background(id self) {
    UIView *view = Call(self, @selector(view));
    for (UIView *candidate in view.subviews)
        if ([candidate isKindOfClass:UIVisualEffectView.class] || [candidate isKindOfClass:UIImageView.class]) return candidate;
    @try { return [self valueForKey:@"_backgroundView"]; } @catch (...) { return nil; }
}
static void RemoveWallpaper(id self) {
    UIView *wall = objc_getAssociatedObject(self, "plampy.wallpaper");
    UIView *blur = objc_getAssociatedObject(self, "plampy.blur");
    [blur removeFromSuperview];
    objc_setAssociatedObject(self, "plampy.blur", nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    [wall removeFromSuperview];
    objc_setAssociatedObject(self, "plampy.wallpaper", nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}
static void ReconcileWallpaper(id self) {
    if (!gEnabled || !gWallpaper) { RemoveWallpaper(self); return; }
    UIView *background = Background(self);
    UIImage *image = [UIImage imageWithContentsOfFile:ThemeFile(@"wallpaper.jpeg")];
    if (!background || !image) { RemoveWallpaper(self); return; }
    UIImageView *wall = objc_getAssociatedObject(self, "plampy.wallpaper");
    if (!wall) {
        wall = [[UIImageView alloc] initWithImage:image];
        wall.frame = background.bounds; wall.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        [background insertSubview:wall atIndex:0];
        objc_setAssociatedObject(self, "plampy.wallpaper", wall, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    } else {
        wall.image = image;
        wall.frame = background.bounds;
        if (wall.superview != background) [background insertSubview:wall atIndex:0];
    }
    UIVisualEffectView *blur = objc_getAssociatedObject(self, "plampy.blur");
    if (gBlur && !blur) {
        blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemMaterialDark]];
        blur.frame = wall.bounds; blur.autoresizingMask = wall.autoresizingMask; [wall addSubview:blur];
        objc_setAssociatedObject(self, "plampy.blur", blur, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    } else if (gBlur && blur.superview != wall) {
        blur.frame = wall.bounds;
        [wall addSubview:blur];
    } else if (!gBlur && blur) {
        [blur removeFromSuperview];
        objc_setAssociatedObject(self, "plampy.blur", nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    wall.alpha = [objc_getAssociatedObject(self, "plampy.presented") boolValue] ? 1 : 0;
}
static void overlayLoad(id self, SEL cmd) {
    if (orig_overlayLoad) orig_overlayLoad(self, cmd);
    if (!gOverlays) gOverlays = [NSHashTable weakObjectsHashTable];
    [gOverlays addObject:self];
    dispatch_async(dispatch_get_main_queue(), ^{ ReconcileWallpaper(self); });
}
static void Animate(id self, BOOL show) {
    UIView *wall = objc_getAssociatedObject(self, "plampy.wallpaper");
    if (wall) [UIView animateWithDuration:.25 animations:^{ wall.alpha = (gEnabled && gWallpaper && show) ? 1 : 0; }];
}
static void present(id self, SEL cmd, BOOL animated, id completion) {
    objc_setAssociatedObject(self, "plampy.presented", @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if (orig_present) orig_present(self, cmd, animated, completion);
    ReconcileWallpaper(self); Animate(self, YES);
}
static void dismiss(id self, SEL cmd, BOOL animated, id completion) {
    objc_setAssociatedObject(self, "plampy.presented", @NO, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if (orig_dismiss) orig_dismiss(self, cmd, animated, completion);
    // The diagnostic flush stays: the shipping collector (the CAML diagnostic
    // route) is still installed at M1 and is removed atomically at M2. M1
    // removes only the substitution traces that used this collector.
    CAMLDiagnosticFlushAtDismiss();
    ReconcileWallpaper(self); Animate(self, NO);
}
static void ReloadPrefs(CFNotificationCenterRef center, void *observer, CFStringRef name, const void *object, CFDictionaryRef userInfo) {
    NSUserDefaults *d = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    gEnabled = [d boolForKey:@"kEnabled"]; gWallpaper = [d boolForKey:@"kWallpaperSwitch"]; gBlur = [d boolForKey:@"kBlurEffectSwitch"]; gTheme = [d integerForKey:@"kThemeType"];
    dispatch_async(dispatch_get_main_queue(), ^{
        for (id overlay in gOverlays) ReconcileWallpaper(overlay);
        CAMLReconcilePackageConsumers();
    });
}
static void Install(Class cls, SEL sel, IMP imp, IMP *orig) { if (HasMethod(cls, sel)) MSHookMessageEx(cls, sel, imp, orig); }
bool PlampyCCFunctionalEnabled(void) { return gEnabled; }
int PlampyCCThemeType(void) { return (int)gTheme; }
__attribute__((constructor)) static void init_plampycc(void) {
    ReloadPrefs(NULL, NULL, NULL, NULL, NULL);
    CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL, ReloadPrefs, (__bridge CFStringRef)kPrefsChanged, NULL, CFNotificationSuspensionBehaviorDeliverImmediately);
    // M1 stock boundary: no static, compact, Flashlight, or header glyph hook
    // is installed from this constructor. The only hooks installed here are the
    // overlay lifecycle hooks that own wallpaper/blur presentation.
    Class overlay = NSClassFromString(@"CCUIModularControlCenterOverlayViewController");
    Install(overlay, @selector(viewDidLoad), (IMP)overlayLoad, (IMP *)&orig_overlayLoad);
    Install(overlay, @selector(presentAnimated:withCompletionHandler:), (IMP)present, (IMP *)&orig_present);
    Install(overlay, @selector(dismissAnimated:withCompletionHandler:), (IMP)dismiss, (IMP *)&orig_dismiss);
}

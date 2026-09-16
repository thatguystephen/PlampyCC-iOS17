// PlampyCC 1.0.2 clean-room reconstruction for iOS 17.3.
// CAML package routing is intentionally bounded by CAML-ROUTING-BLOCKER.md.
#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>
#import <CoreFoundation/CoreFoundation.h>

#ifndef ROOT_PATH_NS
#define ROOT_PATH_NS(path) path
#endif

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";
static BOOL gEnabled, gWallpaper, gBlur;
static NSInteger gTheme;
static void (*orig_layout)(id, SEL), (*orig_roundMove)(id, SEL);
static void (*orig_buttonPackage)(id, SEL, id), (*orig_roundPackage)(id, SEL, id), (*orig_sliderPackage)(id, SEL, id);
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);

static NSString *ThemeName(void) { return gTheme == 1 ? @"Pulsar" : @"Plampy"; }
static NSString *AssetRoot(void) {
    return ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC");
}
static NSString *ThemeRoot(void) { return [AssetRoot() stringByAppendingPathComponent:ThemeName()]; }
static BOOL HasMethod(Class cls, SEL sel) { return cls && class_getInstanceMethod(cls, sel) != NULL; }
static id Call(id obj, SEL sel) {
    return obj && [obj respondsToSelector:sel] ? ((id(*)(id, SEL))objc_msgSend)(obj, sel) : nil;
}

static UIImage *IconImage(NSString *name) {
    NSString *path = [[ThemeRoot() stringByAppendingPathComponent:@"Icon"] stringByAppendingPathComponent:[name stringByAppendingString:@".png"]];
    UIImage *image = [UIImage imageWithContentsOfFile:path];
    // Pulsar intentionally falls back to the complete Plampy icon set when it has no equivalent PNG.
    if (!image && gTheme == 1) {
        path = [[[AssetRoot() stringByAppendingPathComponent:@"Plampy"] stringByAppendingPathComponent:@"Icon"] stringByAppendingPathComponent:[name stringByAppendingString:@".png"]];
        image = [UIImage imageWithContentsOfFile:path];
    }
    return image;
}
static void SetIcon(id view, NSString *name) {
    UIImage *image = IconImage(name);
    if (image && [view respondsToSelector:@selector(setGlyphImage:)])
        ((void(*)(id, SEL, id))objc_msgSend)(view, @selector(setGlyphImage:), image);
    // No image means preserve the original glyph; never replace it with nil.
}
static NSString *IconForIdentifier(NSString *identifier) {
    static NSDictionary *icons;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        icons = @{ @"com.apple.camera": @"Camera", @"com.apple.calculator": @"Calculator",
                   @"com.apple.BarcodeScanner": @"QRCode", @"com.apple.VoiceMemos": @"VoiceMemos",
                   @"com.apple.Magnifier": @"Magnifier" };
    });
    return icons[identifier];
}

static void buttonLayout(id self, SEL _cmd) {
    if (orig_layout) orig_layout(self, _cmd);
    if (!gEnabled) return;
    id controller = Call(self, NSSelectorFromString(@"_viewControllerForAncestor"));
    NSString *identifier = Call(Call(controller, @selector(module)), @selector(applicationIdentifier));
    NSString *icon = IconForIdentifier(identifier);
    if (icon) SetIcon(self, icon);
}
static void roundMove(id self, SEL _cmd) {
    if (orig_roundMove) orig_roundMove(self, _cmd);
    // Round-button state is owned by ControlCenter; CAML routing is not guessed here.
}
static void buttonPackage(id self, SEL sel, id package) {
    if (orig_buttonPackage) orig_buttonPackage(self, sel, package);
}
static void roundPackage(id self, SEL sel, id package) {
    if (orig_roundPackage) orig_roundPackage(self, sel, package);
}
static void sliderPackage(id self, SEL sel, id package) {
    if (orig_sliderPackage) orig_sliderPackage(self, sel, package);
}

static UIView *Background(id self) {
    UIView *view = Call(self, @selector(view));
    for (UIView *candidate in view.subviews)
        if ([candidate isKindOfClass:UIVisualEffectView.class] || [candidate isKindOfClass:UIImageView.class]) return candidate;
    @try { return [self valueForKey:@"_backgroundView"]; } @catch (...) { return nil; }
}
static void overlayLoad(id self, SEL sel) {
    if (orig_overlayLoad) orig_overlayLoad(self, sel);
    if (!gEnabled || !gWallpaper || objc_getAssociatedObject(self, "plampy.wallpaper")) return;
    UIView *background = Background(self);
    UIImage *image = [UIImage imageWithContentsOfFile:[ThemeRoot() stringByAppendingPathComponent:@"wallpaper.jpeg"]];
    if (!background || !image) return;
    UIImageView *wall = [[UIImageView alloc] initWithImage:image];
    wall.frame = background.bounds; wall.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    wall.alpha = 0; [background insertSubview:wall atIndex:0];
    objc_setAssociatedObject(self, "plampy.wallpaper", wall, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if (gBlur) {
        UIVisualEffectView *blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemMaterialDark]];
        blur.frame = wall.bounds; blur.autoresizingMask = wall.autoresizingMask; [wall addSubview:blur];
    }
}
static void animate(id self, BOOL show) {
    UIView *wall = objc_getAssociatedObject(self, "plampy.wallpaper");
    if (wall) [UIView animateWithDuration:.25 animations:^{ wall.alpha = show ? 1 : 0; }];
}
static void present(id self, SEL sel, BOOL animated, id completion) {
    if (orig_present) orig_present(self, sel, animated, completion); animate(self, YES);
}
static void dismiss(id self, SEL sel, BOOL animated, id completion) {
    if (orig_dismiss) orig_dismiss(self, sel, animated, completion); animate(self, NO);
}
static void ReloadPrefs(CFNotificationCenterRef center, void *observer, CFStringRef name, const void *object, CFDictionaryRef userInfo) {
    NSUserDefaults *d = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    gEnabled = [d boolForKey:@"kEnabled"]; gWallpaper = [d boolForKey:@"kWallpaperSwitch"]; gBlur = [d boolForKey:@"kBlurEffectSwitch"]; gTheme = [d integerForKey:@"kThemeType"];
}
static void Install(Class cls, SEL sel, IMP imp, IMP *orig) {
    if (HasMethod(cls, sel)) MSHookMessageEx(cls, sel, imp, (void **)orig);
}
__attribute__((constructor)) static void init_plampycc(void) {
    ReloadPrefs(NULL, NULL, NULL, NULL, NULL);
    CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL, ReloadPrefs, (__bridge CFStringRef)kPrefsChanged, NULL, CFNotificationSuspensionBehaviorDeliverImmediately);
    if (!gEnabled) return;
    Class button = NSClassFromString(@"CCUIButtonModuleView");
    Install(button, @selector(layoutSubviews), (IMP)buttonLayout, (IMP *)&orig_layout);
    Install(button, @selector(setGlyphPackageDescription:), (IMP)buttonPackage, (IMP *)&orig_buttonPackage);
    Class round = NSClassFromString(@"CCUIRoundButton");
    Install(round, @selector(didMoveToWindow), (IMP)roundMove, (IMP *)&orig_roundMove);
    Install(round, @selector(setGlyphPackageDescription:), (IMP)roundPackage, (IMP *)&orig_roundPackage);
    Install(NSClassFromString(@"CCUIContinuousSliderView"), @selector(setGlyphPackageDescription:), (IMP)sliderPackage, (IMP *)&orig_sliderPackage);
    Class overlay = NSClassFromString(@"CCUIModularControlCenterOverlayViewController");
    Install(overlay, @selector(viewDidLoad), (IMP)overlayLoad, (IMP *)&orig_overlayLoad);
    Install(overlay, @selector(presentAnimated:withCompletionHandler:), (IMP)present, (IMP *)&orig_present);
    Install(overlay, @selector(dismissAnimated:withCompletionHandler:), (IMP)dismiss, (IMP *)&orig_dismiss);
}

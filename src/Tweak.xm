// PlampyCC 1.0.2 clean-room reconstruction for iOS 17.3.
// CAML package routing remains pass-through until CAML-ROUTING-BLOCKER.md is cleared.
#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>
#import <CoreFoundation/CoreFoundation.h>
#import <rootless.h>
#import "CAMLDiagnostic.h"

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";
static BOOL gEnabled, gWallpaper, gBlur;
static NSInteger gTheme;
static NSHashTable *gOverlays, *gGlyphViews;
static void (*orig_layout)(id, SEL), (*orig_roundMove)(id, SEL);
static void (*orig_buttonPackage)(id, SEL, id), (*orig_roundPackage)(id, SEL, id), (*orig_sliderPackage)(id, SEL, id);
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);

static NSString *ThemeName(void) { return gTheme == 1 ? @"Pulsar" : @"Plampy"; }
static NSString *AssetRoot(void) { return ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC"); }
static NSString *ThemeRoot(void) { return [AssetRoot() stringByAppendingPathComponent:ThemeName()]; }
static BOOL HasMethod(Class cls, SEL sel) { return cls && class_getInstanceMethod(cls, sel) != NULL; }
static id Call(id obj, SEL sel) { return obj && [obj respondsToSelector:sel] ? ((id(*)(id, SEL))objc_msgSend)(obj, sel) : nil; }

static NSString *IconForIdentifier(NSString *identifier) {
    static NSDictionary *icons;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ icons = @{
        @"com.apple.camera": @"Camera", @"com.apple.calculator": @"Calculator",
        @"com.apple.BarcodeScanner": @"QRCode", @"com.apple.VoiceMemos": @"VoiceMemos",
        @"com.apple.Magnifier": @"Magnifier" }; });
    return icons[identifier];
}
static UIImage *IconImage(NSString *name) {
    NSString *file = [name stringByAppendingString:@".png"];
    UIImage *image = [UIImage imageWithContentsOfFile:[[ThemeRoot() stringByAppendingPathComponent:@"Icon"] stringByAppendingPathComponent:file]];
    if (!image && gTheme == 1)
        image = [UIImage imageWithContentsOfFile:[[AssetRoot() stringByAppendingPathComponent:@"Plampy/Icon"] stringByAppendingPathComponent:file]];
    return image;
}
static UIImage *GlyphImage(id view) { return Call(view, @selector(glyphImage)); }
static void SetGlyphImage(id view, UIImage *image) {
    ((void(*)(id, SEL, id))objc_msgSend)(view, @selector(setGlyphImage:), image);
}
static BOOL SameImage(UIImage *left, UIImage *right) { return left == right || [left isEqual:right]; }
static NSString *ButtonIdentifier(id view) {
    id controller = Call(view, NSSelectorFromString(@"_viewControllerForAncestor"));
    return Call(Call(controller, @selector(module)), @selector(applicationIdentifier));
}
static void ReleaseGlyphOverride(id view) {
    NSDictionary *state = objc_getAssociatedObject(view, "plampy.glyphOverride");
    if (!state) return;
    if ([view respondsToSelector:@selector(setGlyphImage:)]) {
        UIImage *current = [view respondsToSelector:@selector(glyphImage)] ? GlyphImage(view) : nil;
        if (!current || SameImage(current, state[@"applied"])) SetGlyphImage(view, state[@"original"]);
    }
    objc_setAssociatedObject(view, "plampy.glyphOverride", nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}
static void ReconcileGlyphView(id view) {
    if (![NSThread isMainThread]) {
        dispatch_async(dispatch_get_main_queue(), ^{ ReconcileGlyphView(view); });
        return;
    }
    NSDictionary *state = objc_getAssociatedObject(view, "plampy.glyphOverride");
    NSString *identifier = ButtonIdentifier(view);
    NSString *icon = IconForIdentifier(identifier);
    UIImage *image = icon ? IconImage(icon) : nil;
    BOOL canRead = [view respondsToSelector:@selector(glyphImage)];
    BOOL canWrite = [view respondsToSelector:@selector(setGlyphImage:)];
    if (!gEnabled || !icon || !image || !canRead || !canWrite) {
        ReleaseGlyphOverride(view);
        return;
    }
    UIImage *current = GlyphImage(view);
    if (!current) {
        ReleaseGlyphOverride(view);
        return;
    }
    if (state && ![state[@"identifier"] isEqual:identifier]) {
        ReleaseGlyphOverride(view);
        state = nil;
        current = GlyphImage(view);
        if (!current) return;
    }
    UIImage *original = state ? state[@"original"] : current;
    if (state && !SameImage(current, state[@"applied"])) original = current;
    if (!SameImage(current, image)) SetGlyphImage(view, image);
    objc_setAssociatedObject(view, "plampy.glyphOverride", @{ @"identifier": identifier, @"original": original, @"applied": image }, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}
static void buttonLayout(id self, SEL cmd) {
    if (orig_layout) orig_layout(self, cmd);
    if (!gGlyphViews) gGlyphViews = [NSHashTable weakObjectsHashTable];
    [gGlyphViews addObject:self];
    ReconcileGlyphView(self);
}
static void roundMove(id self, SEL cmd) { if (orig_roundMove) orig_roundMove(self, cmd); }
static void buttonPackage(id self, SEL cmd, id package) { if (orig_buttonPackage) orig_buttonPackage(self, cmd, package); }
static void roundPackage(id self, SEL cmd, id package) { if (orig_roundPackage) orig_roundPackage(self, cmd, package); }
static void sliderPackage(id self, SEL cmd, id package) { if (orig_sliderPackage) orig_sliderPackage(self, cmd, package); }

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
    UIImage *image = [UIImage imageWithContentsOfFile:[ThemeRoot() stringByAppendingPathComponent:@"wallpaper.jpeg"]];
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
    CAMLDiagnosticFlushAtDismiss();
    ReconcileWallpaper(self); Animate(self, NO);
}
static void ReloadPrefs(CFNotificationCenterRef center, void *observer, CFStringRef name, const void *object, CFDictionaryRef userInfo) {
    NSUserDefaults *d = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    gEnabled = [d boolForKey:@"kEnabled"]; gWallpaper = [d boolForKey:@"kWallpaperSwitch"]; gBlur = [d boolForKey:@"kBlurEffectSwitch"]; gTheme = [d integerForKey:@"kThemeType"];
    dispatch_async(dispatch_get_main_queue(), ^{
        for (id view in gGlyphViews) ReconcileGlyphView(view);
        for (id overlay in gOverlays) ReconcileWallpaper(overlay);
    });
}
static void Install(Class cls, SEL sel, IMP imp, IMP *orig) { if (HasMethod(cls, sel)) MSHookMessageEx(cls, sel, imp, orig); }
__attribute__((constructor)) static void init_plampycc(void) {
    ReloadPrefs(NULL, NULL, NULL, NULL, NULL);
    CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(), NULL, ReloadPrefs, (__bridge CFStringRef)kPrefsChanged, NULL, CFNotificationSuspensionBehaviorDeliverImmediately);
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
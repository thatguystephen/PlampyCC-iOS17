// PlampyCC 1.0.2 clean-room reconstruction for iOS 17.3.
// Animated CAML routing runs the verified construct-and-pass route in
// src/CAMLReplacement.xm through the three verified setter seams; this file
// owns static glyphs, wallpaper/blur, and the functional preference state.
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
static NSHashTable *gOverlays, *gGlyphViews;
static NSMutableDictionary<NSString *, id> *gIconImages;
static void (*orig_layout)(id, SEL), (*orig_roundMove)(id, SEL);
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);

static NSString *ThemeName(void) { return gTheme == 1 ? @"Pulsar" : @"Plampy"; }
static NSArray<NSString *> *AssetRoots(void) {
    return @[ ROOT_PATH_NS(@"/Library/Application Support/PlampyCC"),
              ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC") ];
}
static BOOL HasMethod(Class cls, SEL sel) { return cls && class_getInstanceMethod(cls, sel) != NULL; }
static id Call(id obj, SEL sel) { return obj && [obj respondsToSelector:sel] ? ((id(*)(id, SEL))objc_msgSend)(obj, sel) : nil; }

static NSString *ThemeFile(NSString *relativePath) {
    for (NSString *root in AssetRoots()) {
        NSString *candidate = [[root stringByAppendingPathComponent:ThemeName()]
            stringByAppendingPathComponent:relativePath];
        if ([[NSFileManager defaultManager] fileExistsAtPath:candidate]) return candidate;
    }
    return nil;
}

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
    if (!gIconImages) gIconImages = [NSMutableDictionary dictionary];
    NSString *cacheKey = [NSString stringWithFormat:@"%ld:%@", (long)gTheme, name];
    id cached = gIconImages[cacheKey];
    if (cached) return cached == NSNull.null ? nil : cached;
    NSString *relative = [@"Icon" stringByAppendingPathComponent:
                          [name stringByAppendingString:@".png"]];
    NSString *path = ThemeFile(relative);
    if (!path && gTheme == 1) {
        for (NSString *root in AssetRoots()) {
            NSString *candidate = [[root stringByAppendingPathComponent:@"Plampy"]
                stringByAppendingPathComponent:relative];
            if ([[NSFileManager defaultManager] fileExistsAtPath:candidate]) {
                path = candidate;
                break;
            }
        }
    }
    UIImage *image = path ? [UIImage imageWithContentsOfFile:path] : nil;
    gIconImages[cacheKey] = image ?: (id)NSNull.null;
    return image;
}
static UIImage *GlyphImage(id view) { return Call(view, @selector(glyphImage)); }
static UIImage *SelectedGlyphImage(id view) { return Call(view, @selector(selectedGlyphImage)); }
static void SetGlyphImage(id view, UIImage *image) {
    ((void(*)(id, SEL, id))objc_msgSend)(view, @selector(setGlyphImage:), image);
}
static void SetSelectedGlyphImage(id view, UIImage *image) {
    ((void(*)(id, SEL, id))objc_msgSend)(view, @selector(setSelectedGlyphImage:), image);
}
static BOOL SameImage(UIImage *left, UIImage *right) { return left == right || [left isEqual:right]; }
static id AncestorController(id view) {
    return Call(view, NSSelectorFromString(@"_viewControllerForAncestor"));
}
static NSString *ButtonIdentifier(id view) {
    return Call(Call(AncestorController(view), @selector(module)), @selector(applicationIdentifier));
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
static void ReleaseFlashlightGlyphs(id view) {
    NSDictionary *state = objc_getAssociatedObject(view, "plampy.flashlightGlyphs");
    if (!state) return;
    if ([view respondsToSelector:@selector(setGlyphImage:)]) {
        UIImage *current = GlyphImage(view);
        if (!current || SameImage(current, state[@"appliedGlyph"]))
            SetGlyphImage(view, state[@"originalGlyph"]);
    }
    if ([view respondsToSelector:@selector(setSelectedGlyphImage:)]) {
        UIImage *current = SelectedGlyphImage(view);
        if (!current || SameImage(current, state[@"appliedSelected"])) {
            id original = state[@"originalSelected"];
            SetSelectedGlyphImage(view, [original isKindOfClass:NSNull.class] ? nil : original);
        }
    }
    objc_setAssociatedObject(view, "plampy.flashlightGlyphs", nil,
                             OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}

static void ReconcileFlashlightView(id view) {
    NSDictionary *state = objc_getAssociatedObject(view, "plampy.flashlightGlyphs");
    UIImage *unselected = IconImage(@"FlashlightOff");
    UIImage *selected = IconImage(@"FlashlightOn");
    BOOL canGlyph = [view respondsToSelector:@selector(glyphImage)] &&
                    [view respondsToSelector:@selector(setGlyphImage:)];
    BOOL canSelected = [view respondsToSelector:@selector(selectedGlyphImage)] &&
                       [view respondsToSelector:@selector(setSelectedGlyphImage:)];
    // The glyph slot is the hard requirement. The selected slot is applied
    // only on hosts that expose both the API and the image: 21D50 round/slider
    // glyph hosts may carry only the glyph setter, and such a host is themed
    // in the glyph slot instead of being silently skipped.
    BOOL applySelected = canSelected && selected != nil;
    if (!gEnabled || !unselected || !canGlyph) {
        ReleaseFlashlightGlyphs(view);
        return;
    }
    UIImage *currentGlyph = GlyphImage(view);
    if (!currentGlyph) {
        ReleaseFlashlightGlyphs(view);
        return;
    }
    UIImage *originalGlyph = state && SameImage(currentGlyph, state[@"appliedGlyph"])
                                 ? state[@"originalGlyph"] : currentGlyph;
    if (!SameImage(currentGlyph, unselected)) SetGlyphImage(view, unselected);
    id originalSelected = (id)NSNull.null;
    id appliedSelected = (id)NSNull.null;
    if (applySelected) {
        UIImage *currentSelected = SelectedGlyphImage(view);
        originalSelected = state && SameImage(currentSelected, state[@"appliedSelected"])
                               ? state[@"originalSelected"] : (currentSelected ?: (id)NSNull.null);
        if (!SameImage(currentSelected, selected)) SetSelectedGlyphImage(view, selected);
        appliedSelected = selected;
    }
    objc_setAssociatedObject(view, "plampy.flashlightGlyphs",
                             @{ @"originalGlyph": originalGlyph,
                                @"appliedGlyph": unselected,
                                @"originalSelected": originalSelected,
                                @"appliedSelected": appliedSelected },
                             OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}

static void ReconcileGlyphView(id view) {
    if (![NSThread isMainThread]) {
        dispatch_async(dispatch_get_main_queue(), ^{ ReconcileGlyphView(view); });
        return;
    }
    Class flashlightClass = NSClassFromString(@"CCUIFlashlightModuleViewController");
    if (flashlightClass && [AncestorController(view) isKindOfClass:flashlightClass]) {
        ReleaseGlyphOverride(view);
        ReconcileFlashlightView(view);
        return;
    }
    ReleaseFlashlightGlyphs(view);
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
// Hook-map site 3 parity (evidence/caml-static/orig-hook-map.md;
// docs/CAML-STATIC-ANALYSIS.md §2.2): the original runs the same static glyph
// path from CCUIRoundButton didMoveToWindow as from CCUIButtonModuleView
// layoutSubviews, so round-button-hosted glyphs are reconciled on both sites.
// Glyph writes never re-enter didMoveToWindow, and setter writes converge via
// SameImage plus the identity cache, so this cannot resurrect the layout
// watchdog loop.
static void roundMove(id self, SEL cmd) {
    if (orig_roundMove) orig_roundMove(self, cmd);
    if (!gGlyphViews) gGlyphViews = [NSHashTable weakObjectsHashTable];
    [gGlyphViews addObject:self];
    ReconcileGlyphView(self);
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
    CAMLDiagnosticFlushAtDismiss();
    ReconcileWallpaper(self); Animate(self, NO);
}
static void ReloadPrefs(CFNotificationCenterRef center, void *observer, CFStringRef name, const void *object, CFDictionaryRef userInfo) {
    NSUserDefaults *d = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    gEnabled = [d boolForKey:@"kEnabled"]; gWallpaper = [d boolForKey:@"kWallpaperSwitch"]; gBlur = [d boolForKey:@"kBlurEffectSwitch"]; gTheme = [d integerForKey:@"kThemeType"];
    dispatch_async(dispatch_get_main_queue(), ^{
        [gIconImages removeAllObjects];
        for (id view in gGlyphViews) ReconcileGlyphView(view);
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
    Class button = NSClassFromString(@"CCUIButtonModuleView");
    Install(button, @selector(layoutSubviews), (IMP)buttonLayout, (IMP *)&orig_layout);
    Class round = NSClassFromString(@"CCUIRoundButton");
    Install(round, @selector(didMoveToWindow), (IMP)roundMove, (IMP *)&orig_roundMove);
    Class overlay = NSClassFromString(@"CCUIModularControlCenterOverlayViewController");
    Install(overlay, @selector(viewDidLoad), (IMP)overlayLoad, (IMP *)&orig_overlayLoad);
    Install(overlay, @selector(presentAnimated:withCompletionHandler:), (IMP)present, (IMP *)&orig_present);
    Install(overlay, @selector(dismissAnimated:withCompletionHandler:), (IMP)dismiss, (IMP *)&orig_dismiss);
}
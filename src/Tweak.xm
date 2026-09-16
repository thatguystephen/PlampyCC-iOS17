// PlampyCC 1.0.2 clean-room reconstruction for iOS 17.3.
// Original attribution: sugiuta / CyPwn package metadata. No original source is claimed.
#import <UIKit/UIKit.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <substrate.h>

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static BOOL gEnabled = NO, gWallpaper = NO, gBlur = NO;
static NSInteger gTheme = 0;
static void (*orig_layout)(id, SEL), (*orig_roundMove)(id, SEL);
static void (*orig_buttonPackage)(id, SEL, id), (*orig_roundPackage)(id, SEL, id), (*orig_sliderPackage)(id, SEL, id);
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);

static NSString *ThemeName(void) { return gTheme == 1 ? @"Pulsar" : @"Plampy"; }
static NSString *AssetRoot(void) { return [@"/var/mobile/Library/Application Support/PlampyCC" stringByAppendingPathComponent:ThemeName()]; }
static NSString *MappedBundle(NSString *name) {
    static NSDictionary *map;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ map = @{ @"Brightness": @"DisplayModule.bundle", @"Volume": @"MediaControls.framework", @"timer": @"TimerModule.bundle" }; });
    return map[name];
}
static BOOL HasMethod(Class cls, SEL sel) { return cls && class_getInstanceMethod(cls, sel) != NULL; }
static id Call(id obj, SEL sel) { return obj && [obj respondsToSelector:sel] ? ((id(*)(id,SEL))objc_msgSend)(obj,sel) : nil; }
static void SetImage(id view, NSString *imageName, NSString *bundle) {
    if (!view || !bundle) return;
    NSString *path = [[AssetRoot() stringByAppendingPathComponent:@"Assets"] stringByAppendingPathComponent:bundle];
    path = [path stringByAppendingPathComponent:@"Assets.car"];
    Class catalog = NSClassFromString(@"CUICatalog");
    if (!catalog || ![catalog instancesRespondToSelector:@selector(initWithURL:error:)]) return;
    id cat = [[catalog alloc] initWithURL:[NSURL fileURLWithPath:path] error:NULL];
    id image = cat ? ((id(*)(id,SEL,id,double))objc_msgSend)(cat, @selector(imageWithName:scaleFactor:), imageName, 1.0) : nil;
    UIImage *ui = image ? [[UIImage alloc] initWithCGImage:[image CGImage]] : nil;
    if (ui && [view respondsToSelector:@selector(setGlyphImage:)]) ((void(*)(id,SEL,id))objc_msgSend)(view,@selector(setGlyphImage:),ui);
}
static void buttonLayout(id self, SEL _cmd) {
    if (orig_layout) orig_layout(self,_cmd); if (!gEnabled) return;
    // Classification is intentionally centralized; unknown modules pass through unchanged.
    id controller = Call(self, NSSelectorFromString(@"_viewControllerForAncestor"));
    NSString *identifier = Call(Call(controller, @selector(module)), @selector(applicationIdentifier));
    NSDictionary *icons = @{ @"com.apple.camera": @"AppIcon", @"com.apple.calculator": @"AppIcon", @"com.apple.BarcodeScanner": @"AppIcon", @"com.apple.VoiceMemos": @"AppIcon", @"com.apple.Magnifier": @"AppIcon" };
    NSString *icon = icons[identifier]; if (icon) SetImage(self, icon, nil);
}
static void roundMove(id self, SEL _cmd) { if (orig_roundMove) orig_roundMove(self,_cmd); if (!gEnabled) return; }
static void packageHook(id self, SEL _cmd, id package) {
    NSString *name = Call(package, @selector(packageName)); NSString *mapped = MappedBundle(name);
    if (mapped && [self respondsToSelector:_cmd]) { /* resolver is shared; unsupported descriptions remain original */ }
    if (_cmd == @selector(setGlyphPackageDescription:) && orig_buttonPackage) orig_buttonPackage(self,_cmd,package);
}
static void buttonPackage(id s, SEL c, id p) { if (orig_buttonPackage) orig_buttonPackage(s,c,p); }
static void roundPackage(id s, SEL c, id p) { if (orig_roundPackage) orig_roundPackage(s,c,p); }
static void sliderPackage(id s, SEL c, id p) { if (orig_sliderPackage) orig_sliderPackage(s,c,p); }
static UIView *Background(id self) {
    if ([self respondsToSelector:@selector(view)]) {
        UIView *view = Call(self,@selector(view));
        for (UIView *candidate in view.subviews) if ([candidate isKindOfClass:UIVisualEffectView.class] || [candidate isKindOfClass:UIImageView.class]) return candidate;
    }
    @try { return [self valueForKey:@"_backgroundView"]; } @catch (...) { return nil; }
}
static void overlayLoad(id self, SEL c) {
    if (orig_overlayLoad) orig_overlayLoad(self,c); if (!gEnabled || !gWallpaper) return;
    UIView *background = Background(self); if (!background) return;
    UIImageView *wall = [[UIImageView alloc] initWithImage:[UIImage imageWithContentsOfFile:[AssetRoot() stringByAppendingPathComponent:@"wallpaper.jpeg"]]];
    wall.frame = background.bounds; wall.autoresizingMask = UIViewAutoresizingFlexibleWidth|UIViewAutoresizingFlexibleHeight; wall.alpha = 0; [background insertSubview:wall atIndex:0];
    objc_setAssociatedObject(self, "plampy.wallpaper", wall, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    if (gBlur) { UIVisualEffectView *blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleSystemMaterialDark]]; blur.frame=wall.bounds; blur.autoresizingMask=wall.autoresizingMask; [wall addSubview:blur]; }
}
static void animate(id self, BOOL show) { UIView *v=objc_getAssociatedObject(self,"plampy.wallpaper"); if (v) [UIView animateWithDuration:.25 animations:^{v.alpha=show?1:0;}]; }
static void present(id s, SEL c, BOOL a, id h) { animate(s,YES); if(orig_present)orig_present(s,c,a,h); }
static void dismiss(id s, SEL c, BOOL a, id h) { animate(s,NO); if(orig_dismiss)orig_dismiss(s,c,a,h); }
static void Install(Class cls, SEL sel, IMP imp, IMP *orig) { if (HasMethod(cls,sel)) MSHookMessageEx(cls,sel,imp,(void **)orig); }
__attribute__((constructor)) static void init_plampycc(void) {
    NSUserDefaults *d = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain]; gEnabled=[d boolForKey:@"kEnabled"]; gWallpaper=[d boolForKey:@"kWallpaperSwitch"]; gBlur=[d boolForKey:@"kBlurEffectSwitch"]; gTheme=[d integerForKey:@"kThemeType"]; if (!gEnabled) return;
    Install(NSClassFromString(@"CCUIButtonModuleView"), @selector(layoutSubviews), (IMP)buttonLayout, (IMP *)&orig_layout);
    Install(NSClassFromString(@"CCUIButtonModuleView"), @selector(setGlyphPackageDescription:), (IMP)buttonPackage, (IMP *)&orig_buttonPackage);
    Install(NSClassFromString(@"CCUIRoundButton"), @selector(didMoveToWindow), (IMP)roundMove, (IMP *)&orig_roundMove);
    Install(NSClassFromString(@"CCUIRoundButton"), @selector(setGlyphPackageDescription:), (IMP)roundPackage, (IMP *)&orig_roundPackage);
    Install(NSClassFromString(@"CCUIContinuousSliderView"), @selector(setGlyphPackageDescription:), (IMP)sliderPackage, (IMP *)&orig_sliderPackage);
    Class overlay=NSClassFromString(@"CCUIModularControlCenterOverlayViewController"); Install(overlay,@selector(viewDidLoad),(IMP)overlayLoad,(IMP *)&orig_overlayLoad); Install(overlay,@selector(presentAnimated:withCompletionHandler:),(IMP)present,(IMP *)&orig_present); Install(overlay,@selector(dismissAnimated:withCompletionHandler:),(IMP)dismiss,(IMP *)&orig_dismiss);
}

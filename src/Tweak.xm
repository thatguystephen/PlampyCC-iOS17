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
#include <string.h>
#include <cmath>
#include "FlashlightOpticalPolicy.hpp"

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";
static BOOL gEnabled, gWallpaper, gBlur;
static NSInteger gTheme;
static NSHashTable *gOverlays, *gGlyphViews;
static NSMutableDictionary<NSString *, id> *gIconImages;
static void (*orig_layout)(id, SEL), (*orig_roundMove)(id, SEL);
static void (*orig_overlayLoad)(id, SEL), (*orig_present)(id, SEL, BOOL, id), (*orig_dismiss)(id, SEL, BOOL, id);
static void (*orig_headerGlyph)(id, SEL, id, double);

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
// Sized glyph rendering: t_4b68c639 established UIImage canvas sizing as
// an effective control after a content-only shrink (56x80 -> 44x62 within
// 80x144) left device output unchanged. Matching the stock canvas fixed the
// oversized raw raster but IMG_1095.JPG shows that equality is not optical
// equality: the custom raster has transparent padding and a different shape
// from the stock SF Symbol. Compact callers now apply the measured policy in
// FlashlightOpticalPolicy.hpp; the expanded header keeps scale 1.0.
// The 25x48 fallback retains the original currentImage construction evidence
// (evidence/caml-static/orig-arm64-layoutglyphs.dis.txt, 0x81b4/0x81f4/
// 0x712c-0x7154). Art remains centered/aspect-fit. Cache identity includes
// theme, name, source canvas and optical policy, not just output dimensions.
static NSMutableDictionary<NSString *, id> *gSizedArt;
static char kGlyphSourceCanvas;
static UIImage *SizedGlyphArt(NSString *name, CGSize canvas, CGFloat opticalScale = 1.0) {
    if (!std::isfinite(canvas.width) || !std::isfinite(canvas.height)) return nil;
    if (canvas.width <= 0 || canvas.height <= 0) canvas = CGSizeMake(25.0, 48.0);
    UIImage *art = IconImage(name);
    if (![art isKindOfClass:UIImage.class]) return nil;
    if (!gSizedArt) gSizedArt = [NSMutableDictionary dictionary];
    NSString *key = [NSString stringWithFormat:@"%ld:%@:%.3f:%.3f:%.9f",
                     (long)gTheme, name, canvas.width, canvas.height, opticalScale];
    id cached = gSizedArt[key];
    if (cached) return cached == NSNull.null ? nil : cached;
    NSValue *sourceCanvas = [NSValue valueWithCGSize:canvas];
    canvas.width *= opticalScale;
    canvas.height *= opticalScale;
    UIImage *rendered = nil;
    UIGraphicsBeginImageContextWithOptions(canvas, NO, 0);
    CGFloat scale = MIN(canvas.width / art.size.width, canvas.height / art.size.height);
    CGSize draw = CGSizeMake(art.size.width * scale, art.size.height * scale);
    [art drawInRect:CGRectMake((canvas.width - draw.width) / 2.0,
                               (canvas.height - draw.height) / 2.0,
                               draw.width, draw.height)];
    rendered = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();
    if (rendered) objc_setAssociatedObject(rendered, &kGlyphSourceCanvas,
                                           sourceCanvas, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    gSizedArt[key] = rendered ?: (id)NSNull.null;
    return rendered;
}
// Both the intercepted setter and reconciliation can receive our own output.
// Recover its stock canvas before scaling, including after preference cache
// invalidation. Metadata belongs to the image, not to a cache entry or a view.
static UIImage *SizedCompactGlyphArt(NSString *name, UIImage *peer) {
    NSValue *sourceCanvas = objc_getAssociatedObject(peer, &kGlyphSourceCanvas);
    CGSize canvas = sourceCanvas ? [sourceCanvas CGSizeValue] : peer.size;
    return SizedGlyphArt(name, canvas, flashlight_optical::kCompactScale);
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
// Diagnostic glyph trace (docs/FLASHLIGHT-DIAGNOSTIC.md): one
// approved outcome token per reconciler decision. ObserveGlyph is a pure
// observer behind the collector's compile-time gate and admission check, so
// release builds record nothing and reconciliation behavior is unchanged.
static void TraceGlyph(id view, const char *outcome) {
    ObserveGlyph(view, outcome, "glyph-recon");
}
// Post-apply stability probe: re-reads the glyph slot after a short delay to
// distinguish "we never applied" from "we applied and something re-wrote the
// stock glyph". Read-only by contract (no setter, no layout invalidation), so
// it cannot perturb the SameImage/watchdog convergence.
static void ScheduleGlyphStabilityCheck(id view, UIImage *appliedGlyph) {
    if (!CAMLDiagnosticPrimitiveAdmission(false)) return;
    __weak id weakView = view;
    UIImage *expected = appliedGlyph;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        id strongView = weakView;
        if (!strongView) {
            ObserveGlyph(nil, "stable-gone", "glyph-probe");
            return;
        }
        UIImage *current = GlyphImage(strongView);
        const char *outcome = !current ? "stable-miss"
                             : SameImage(current, expected) ? "stable-kept"
                             : "stable-repl";
        ObserveGlyph(strongView, outcome, "glyph-probe");
    });
}
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
    // State-to-art mapping ([ADDRESS], authoritative device observation on
    // 21D50): the normal glyph slot is displayed while the flashlight is OFF
    // and the selected slot while it is ON, so the resting slot carries the
    // FlashlightOff art and the active slot the FlashlightOn art. The original
    // tweak's route shape (evidence/caml-static/orig-arm64-layoutglyphs.dis.txt
    // 0x81a4/0x8218: FlashlightOn -> setGlyphImage:) renders reversed against
    // that observation and is deliberately not reproduced. Both images are
    // rendered from the stock source canvas with the compact optical policy;
    // source metadata prevents our own output from becoming a new baseline.
    UIImage *onArt = IconImage(@"FlashlightOn");
    UIImage *offArt = IconImage(@"FlashlightOff");
    BOOL canGlyph = [view respondsToSelector:@selector(glyphImage)] &&
                    [view respondsToSelector:@selector(setGlyphImage:)];
    BOOL canSelected = [view respondsToSelector:@selector(selectedGlyphImage)] &&
                       [view respondsToSelector:@selector(setSelectedGlyphImage:)];
    // The glyph slot is the hard requirement. The selected slot is applied
    // only on hosts that expose both the API and the image: 21D50 round/slider
    // glyph hosts may carry only the glyph setter, and such a host is themed
    // in the glyph slot instead of being silently skipped.
    BOOL applySelected = canSelected && onArt != nil;
    if (!gEnabled || !offArt || !canGlyph) {
        TraceGlyph(view, !gEnabled ? "skip-disable"
                                  : (!canGlyph ? "skip-no-api" : "skip-no-img"));
        ReleaseFlashlightGlyphs(view);
        return;
    }
    UIImage *currentGlyph = GlyphImage(view);
    if (!currentGlyph) {
        TraceGlyph(view, "skip-nil");
        ReleaseFlashlightGlyphs(view);
        return;
    }
    UIImage *offGlyph = SizedCompactGlyphArt(@"FlashlightOff", currentGlyph);
    UIImage *onGlyph = SizedCompactGlyphArt(@"FlashlightOn", currentGlyph);
    if (!offGlyph) {
        TraceGlyph(view, "skip-no-img");
        ReleaseFlashlightGlyphs(view);
        return;
    }
    applySelected = applySelected && onGlyph != nil;
    UIImage *originalGlyph = state && SameImage(currentGlyph, state[@"appliedGlyph"])
                                 ? state[@"originalGlyph"] : currentGlyph;
    if (!SameImage(currentGlyph, offGlyph)) SetGlyphImage(view, offGlyph);
    id originalSelected = (id)NSNull.null;
    id appliedSelected = (id)NSNull.null;
    if (applySelected) {
        UIImage *currentSelected = SelectedGlyphImage(view);
        originalSelected = state && SameImage(currentSelected, state[@"appliedSelected"])
                               ? state[@"originalSelected"] : (currentSelected ?: (id)NSNull.null);
        if (!SameImage(currentSelected, onGlyph)) SetSelectedGlyphImage(view, onGlyph);
        appliedSelected = onGlyph;
    }
    objc_setAssociatedObject(view, "plampy.flashlightGlyphs",
                             @{ @"originalGlyph": originalGlyph,
                                @"appliedGlyph": offGlyph,
                                @"originalSelected": originalSelected,
                                @"appliedSelected": appliedSelected },
                             OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    TraceGlyph(view, applySelected ? "glyph-sel-ap" : "glyph-appl");
    ScheduleGlyphStabilityCheck(view, offGlyph);
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
        TraceGlyph(view, !gEnabled ? "skip-disable"
                                  : (!canRead || !canWrite ? "skip-no-api"
                                                          : (!icon ? "skip-no-icon" : "skip-no-img")));
        ReleaseGlyphOverride(view);
        return;
    }
    UIImage *current = GlyphImage(view);
    if (!current) {
        TraceGlyph(view, "skip-nil");
        ReleaseGlyphOverride(view);
        return;
    }
    if (state && ![state[@"identifier"] isEqual:identifier]) {
        ReleaseGlyphOverride(view);
        state = nil;
        current = GlyphImage(view);
        if (!current) {
            TraceGlyph(view, "skip-id-nil");
            return;
        }
    }
    UIImage *original = state ? state[@"original"] : current;
    if (state && !SameImage(current, state[@"applied"])) original = current;
    if (!SameImage(current, image)) SetGlyphImage(view, image);
    objc_setAssociatedObject(view, "plampy.glyphOverride", @{ @"identifier": identifier, @"original": original, @"applied": image }, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    TraceGlyph(view, "generic-app");
    ScheduleGlyphStabilityCheck(view, image);
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

// Flashlight header-glyph substitution for
// -[CCUIFlashlightBackgroundViewController setHeaderGlyphImage:unscaledSymbolPointSize:].
// The pushed stock image carries the flashlight state. Classification is
// pinned to the positive off identity only (the plain, point-size-configured,
// or _symbolName form of flashlight.off.fill): the module pushes per-level
// variants for the on state (evidence/ios17-module-glyph-seams-21D50.md
// section 2), and pinning the on symbol instead collapsed every level variant
// into the off branch ([ADDRESS]), so anything not positively
// identified as off is the on state. The substituted art is rendered through
// SizedGlyphArt at the pushed image's own canvas (the stock symbol is the
// sizing peer) and memoized, so the setter converges on image identity exactly
// like the static glyph path.
static UIImage *HeaderGlyphSubstitute(UIImage *image, double pointSize) {
    if (!image) return nil;  // a nil push carries no state to theme: fail open
    static NSString * const kFlashlightOffSymbol = @"flashlight.off.fill";
    BOOL off = NO;
    UIImage *plain = [UIImage systemImageNamed:kFlashlightOffSymbol];
    if (image == plain) {
        off = YES;
    } else if (pointSize > 0) {
        UIImageSymbolConfiguration *configuration = [UIImageSymbolConfiguration configurationWithPointSize:pointSize];
        UIImage *sized = configuration ? [UIImage systemImageNamed:kFlashlightOffSymbol withConfiguration:configuration] : nil;
        off = sized && image == sized;
    }
    if (!off) {
        NSString *symbolName = Call(image, NSSelectorFromString(@"_symbolName"));
        off = [symbolName isKindOfClass:NSString.class] && [symbolName isEqualToString:kFlashlightOffSymbol];
    }
    NSString *name = off ? @"FlashlightOff" : @"FlashlightOn";
    UIImage *themed = SizedGlyphArt(name, image.size);
    // Fail open on a nil, missing, or invalid themed image: the caller's own
    // image is forwarded unchanged instead of a broken substitution.
    return [themed isKindOfClass:UIImage.class] ? themed : nil;
}
static void headerGlyph(id self, SEL cmd, UIImage *image, double pointSize) {
    UIImage *argument = image;
    // Forwarding-decision trace (docs/FLASHLIGHT-DIAGNOSTIC.md): one approved
    // token per hook verdict, recorded before the original is invoked. The
    // input-side header-glyph observer records the caller's push from outside
    // the chain, so it cannot show what this hook forwarded; only this token
    // distinguishes a themed substitution from a forward of the caller's own
    // image. The fixed token is the whole verdict — no path, pointer, or
    // identifier rides with it.
    const char *decision = "hdr-bypass";
    Class flashlightClass = NSClassFromString(@"CCUIFlashlightBackgroundViewController");
    // Exact receiver class and existing functional state only: subclass
    // instances, every other class, and a disabled tweak forward the caller's
    // arguments unchanged.
    if (gEnabled && flashlightClass && object_getClass(self) == flashlightClass) {
        UIImage *themed = HeaderGlyphSubstitute(image, pointSize);
        if (themed) argument = themed;
        decision = themed ? "hdr-subst" : "hdr-failop";
    }
    ObserveGlyph(self, decision, "header-hook");
    if (orig_headerGlyph) orig_headerGlyph(self, cmd, argument, pointSize);
}
// ABI-checked install: the hook is the verified object + 64-bit CGFloat form
// of -setHeaderGlyphImage:unscaledSymbolPointSize: (v32@0:8@16d24, the same
// verified seam as the header-glyph observer site in src/CAMLDiagnostic.xm).
// Runtime encodings may quote class annotations; the shape is compared after
// stripping them (the ABIShapeMatches policy) and any mismatch refuses the
// hook, leaving the stock header glyph in place.
static BOOL HeaderGlyphEncodingMatches(const char *runtimeEncoding) {
    static const char kExpected[] = "v32@0:8@16d24";
    if (!runtimeEncoding) return NO;
    char normalized[96] = {};
    size_t out = 0;
    for (size_t i = 0; runtimeEncoding[i] != '\0' && out + 1 < sizeof(normalized); ++i) {
        if (runtimeEncoding[i] == '@' && runtimeEncoding[i + 1] == '"') {
            normalized[out++] = '@';
            i += 2;
            while (runtimeEncoding[i] != '\0' && runtimeEncoding[i] != '"') ++i;
            continue;
        }
        normalized[out++] = runtimeEncoding[i];
    }
    normalized[out] = '\0';
    return strcmp(normalized, kExpected) == 0;
}
static void InstallHeaderGlyphHook(Class cls) {
    SEL sel = @selector(setHeaderGlyphImage:unscaledSymbolPointSize:);
    Method method = cls ? class_getInstanceMethod(cls, sel) : NULL;
    if (!method || !HeaderGlyphEncodingMatches(method_getTypeEncoding(method))) return;
    MSHookMessageEx(cls, sel, (IMP)headerGlyph, (IMP *)&orig_headerGlyph);
}

// Compact Flashlight glyph substitution for the two static glyph setters of
// CCUIButtonModuleView. The Flashlight module re-pushes its state SF Symbols
// through these setters on every flashlight level/state update
// (evidence/ios17-module-glyph-seams-21D50.md section 2: per-level
// systemImageNamed:withConfiguration: writes via _updateGlyphForFlashlightLevel:),
// so substitution happens in flight, exactly like the header seam — a one-shot
// layout write cannot hold it (t_fa2754b0). State is deterministic from the
// setter slot, not from a private UIImage symbol name (sized per-level symbols
// defeat name classification), and the slot-to-art mapping follows the
// authoritative device observation (t_4b68c639): the normal setGlyphImage:
// slot displays while the flashlight is OFF and the setSelectedGlyphImage:
// slot while it is ON, so the normal setter carries the FlashlightOff art and
// the selected setter the FlashlightOn art. Each substituted image is rendered
// through SizedCompactGlyphArt using the original stock canvas plus the
// calibrated optical factor, and memoized; a nil push or a nil/missing/invalid
// themed decode fails open to the caller's image.
static UIImage *CompactGlyphSubstitute(UIImage *image, BOOL selectedSlot) {
    if (!image) return nil;
    NSString *name = selectedSlot ? @"FlashlightOn" : @"FlashlightOff";
    if (![IconImage(name) isKindOfClass:UIImage.class]) return nil;
    UIImage *themed = SizedCompactGlyphArt(name, image);
    return [themed isKindOfClass:UIImage.class] ? themed : nil;
}
static UIImage *CompactSubstitutedArgument(id self, UIImage *image, BOOL selectedSlot) {
    Class flashlightClass = NSClassFromString(@"CCUIFlashlightModuleViewController");
    if (gEnabled && flashlightClass && [AncestorController(self) isKindOfClass:flashlightClass]) {
        UIImage *themed = CompactGlyphSubstitute(image, selectedSlot);
        if (themed) return themed;
    }
    return image;
}
static void (*orig_compactGlyph)(id, SEL, UIImage *);
static void (*orig_compactSelected)(id, SEL, UIImage *);
static void compactSetGlyph(id self, SEL cmd, UIImage *image) {
    if (orig_compactGlyph) orig_compactGlyph(self, cmd, CompactSubstitutedArgument(self, image, NO));
}
static void compactSetSelectedGlyph(id self, SEL cmd, UIImage *image) {
    if (orig_compactSelected) orig_compactSelected(self, cmd, CompactSubstitutedArgument(self, image, YES));
}
// ABI-checked install: both seams are the verified object-setter form of the
// compact glyph API (v24@0:8@16 after class-annotation stripping, the same
// normalization policy as the header gate). Any shape mismatch refuses that
// hook and leaves the stock compact glyph path untouched.
static BOOL CompactGlyphEncodingMatches(const char *runtimeEncoding) {
    static const char kExpected[] = "v24@0:8@16";
    if (!runtimeEncoding) return NO;
    char normalized[96] = {};
    size_t out = 0;
    for (size_t i = 0; runtimeEncoding[i] != '\0' && out + 1 < sizeof(normalized); ++i) {
        if (runtimeEncoding[i] == '@' && runtimeEncoding[i + 1] == '"') {
            normalized[out++] = '@';
            i += 2;
            while (runtimeEncoding[i] != '\0' && runtimeEncoding[i] != '"') ++i;
            continue;
        }
        normalized[out++] = runtimeEncoding[i];
    }
    normalized[out] = '\0';
    return strcmp(normalized, kExpected) == 0;
}
static void InstallCompactGlyphHooks(Class cls) {
    SEL glyph = @selector(setGlyphImage:);
    Method glyphMethod = cls ? class_getInstanceMethod(cls, glyph) : NULL;
    if (glyphMethod && CompactGlyphEncodingMatches(method_getTypeEncoding(glyphMethod)))
        MSHookMessageEx(cls, glyph, (IMP)compactSetGlyph, (IMP *)&orig_compactGlyph);
    SEL selected = @selector(setSelectedGlyphImage:);
    Method selectedMethod = cls ? class_getInstanceMethod(cls, selected) : NULL;
    if (selectedMethod && CompactGlyphEncodingMatches(method_getTypeEncoding(selectedMethod)))
        MSHookMessageEx(cls, selected, (IMP)compactSetSelectedGlyph, (IMP *)&orig_compactSelected);
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
        [gSizedArt removeAllObjects];
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
    // The compact Flashlight seam lives on the same linked, load-time-registered
    // class (CCUIButtonModuleView is in ControlCenterUIKit, not the lazily
    // loaded Flashlight plugin), so both static glyph setter hooks install
    // here at load; the module gate inside them confines substitution to the
    // Flashlight button and every other receiver forwards unchanged.
    InstallCompactGlyphHooks(button);
    Class round = NSClassFromString(@"CCUIRoundButton");
    Install(round, @selector(didMoveToWindow), (IMP)roundMove, (IMP *)&orig_roundMove);
    Class overlay = NSClassFromString(@"CCUIModularControlCenterOverlayViewController");
    Install(overlay, @selector(viewDidLoad), (IMP)overlayLoad, (IMP *)&orig_overlayLoad);
    Install(overlay, @selector(presentAnimated:withCompletionHandler:), (IMP)present, (IMP *)&orig_present);
    Install(overlay, @selector(dismissAnimated:withCompletionHandler:), (IMP)dismiss, (IMP *)&orig_dismiss);
    // Install against the linked, load-time-registered seam owner — the same
    // class and v32@0:8@16d24 method the header-glyph observer site in
    // src/CAMLDiagnostic.xm hooks at load — not the Flashlight receiver class:
    // CCUIFlashlightBackgroundViewController is defined in the Control Center
    // plugin FlashlightModule.bundle, which loads long after this constructor,
    // so an install-time NSClassFromString of it returns nil and
    // InstallHeaderGlyphHook silently skipped (zero header-hook events,
    // t_724201a5). The exact receiver class gate inside headerGlyph keeps
    // substitution confined to CCUIFlashlightBackgroundViewController; every
    // other receiver of the seam records hdr-bypass and forwards the caller's
    // arguments unchanged.
    Class header = NSClassFromString(@"CCUICustomContentModuleBackgroundViewController");
    InstallHeaderGlyphHook(header);
}
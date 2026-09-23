// Functional animated CAML replacement — verified construct-and-pass route
// with live preference reconciliation.
//
// Evidence: evidence/CAML-ABI-MAP-21D50.md (21D50, iPhone15,2), §2-§4.
// This module only ever uses the declarations in src/CAMLVerifiedABI.h: the
// package-description initializer, packageURL, and the glyphPackageDescription
// recovery read-back. The three hooked setters are invoked through their
// original-IMP slots (the shim's hook bodies and CAMLInvokeOriginalPackage),
// never through re-declared selectors here. No private URL ivar is ever read
// or written.
//
// Route (ABI map §3): build "<theme root>/Assets/<mapped bundle>" from the
// rooted theme directory, construct a fresh CCUICAPackageDescription with the
// ORIGINAL package name and that bundle, and hand it to the stock setter.
// Every miss (disabled tweak, non-conforming description, consumer without a
// verified recovery read-back, unmapped name, timer under Pulsar,
// bundle/initializer failure, nil resolved packageURL, any exception) fails
// open: the stock description passes through unchanged. No runtime animation
// claim is made by this implementation; the five deferred runtime
// observations are listed in CAML-ROUTING-BLOCKER.md.
//
// Live preference reconciliation (SP1 correction): every intercepted install
// records the newest stock description ("original") and distinguishes our
// owned replacement ("applied") from untouched stock. Consumers are tracked
// weakly (and their records with them), and every preference reload
// reconciles them on the main thread so disabled-start->enable, Plampy<->
// Pulsar theme changes, disable/re-enable, missing or unsupported resources,
// newer stock assignments, and consumer destruction are handled without
// waiting for another setter call. Restoration installs the recorded original
// only while our applied replacement is provably still installed (verified
// read-back), and a newer stock description is adopted as the recovery
// original instead of ever being overwritten.
#import <Foundation/Foundation.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <rootless.h>
#import "CAMLReplacement.h"
#import "CAMLVerifiedABI.h"
#import "PlampyCCState.h"
#include "CAMLReplacementCore.hpp"

extern "C" void CAMLInvokeOriginalPackage(int seam, __unsafe_unretained id consumer,
                                          __unsafe_unretained id description);

static NSString *CAMLThemeRoot(NSString *theme) {
    // Rooted assets base; final install is <base>/<theme>/Assets per the CAML URL contract.
    return [ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC")
        stringByAppendingPathComponent:theme];
}

// Extract the ORIGINAL stock package name (the private packageURL's .ca stem).
// Fail open to a pass-through description if any private accessor is missing.
static NSString *CAMLPackageStem(__unsafe_unretained id description) {
    if (![description respondsToSelector:@selector(packageURL)]) return nil;
    id packageURL = ((id(*)(id, SEL))objc_msgSend)(description, @selector(packageURL));
    if (![packageURL isKindOfClass:[NSURL class]]) return nil;
    NSString *stem = [[(NSURL *)packageURL URLByDeletingPathExtension] lastPathComponent];
    return stem.length > 0 ? stem : nil;
}

// ---- recovery read-back (verified getter, read-only) ----

// Returns NO when the consumer cannot report its installed description; the
// callers then fail open because no verified restoration path exists. A nil
// *outInstalled with YES means "nothing currently installed".
static BOOL ReadInstalledDescription(__unsafe_unretained id consumer, id *outInstalled) {
    SEL selector = @selector(glyphPackageDescription);
    if (!consumer || ![consumer respondsToSelector:selector]) return NO;
    id installed = ((id(*)(id, SEL))objc_msgSend)(consumer, selector);
    if (outInstalled) *outInstalled = installed;
    return YES;
}

static BOOL SameDescription(__unsafe_unretained id left, __unsafe_unretained id right) {
    return left == right || [left isEqual:right];
}

// ---- owned/applied recovery state (per consumer) ----

// State mirrors the proven static-glyph model (plampy.glyphOverride): an
// identity key, the recovery original (newest stock description seen), and the
// owned applied replacement plus the theme it was built for. All references
// are strong but bounded to the consumer's lifetime: the record is an
// associated object and the registry below is weak, so consumer destruction
// releases the record (and its original/applied references) automatically.
static const char kPackageOverrideKey[] = "plampy.packageOverride";
static const char kPackageSeamKey[] = "plampy.packageSeam";

static NSHashTable *PackageConsumers(void) {
    static NSHashTable *consumers;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ consumers = [NSHashTable weakObjectsHashTable]; });
    return consumers;
}

static void StorePackageState(__unsafe_unretained id consumer, NSString *identifier,
                              __unsafe_unretained id original, __unsafe_unretained id applied,
                              NSNumber *appliedTheme) {
    NSMutableDictionary *state = [NSMutableDictionary dictionary];
    if (identifier) state[@"identifier"] = identifier;
    if (original) state[@"original"] = original;
    if (applied) state[@"applied"] = applied;
    if (appliedTheme) state[@"appliedTheme"] = appliedTheme;
    objc_setAssociatedObject(consumer, kPackageOverrideKey, state.count ? state : nil,
                             OBJC_ASSOCIATION_RETAIN_NONATOMIC);
}

// ---- construction boundary (called by the non-ARC shim and the reconcile pass) ----

extern "C" id CAMLCreateReplacementDescription(__unsafe_unretained id consumer,
                                               __unsafe_unretained id description,
                                               bool sliderSite)
    __attribute__((ns_returns_retained)) {
    @try {
        if (!consumer || !description || !PlampyCCFunctionalEnabled()) return nil;
        // Recovery contract: never install an owned replacement where the
        // installed description cannot be read back for verified restoration.
        id probe = nil;
        if (!ReadInstalledDescription(consumer, &probe)) return nil;
        NSString *name = CAMLPackageStem(description);
        if (!name) return nil;

        NSString *theme = PlampyCCThemeType() == 1 ? @"Pulsar" : @"Plampy";
        const char *bundleDirectory =
            caml_replacement::BundleDirectoryForPackage(name.UTF8String,
                                                        sliderSite ? caml_replacement::Site::Slider
                                                                   : caml_replacement::Site::Setter,
                                                        PlampyCCThemeType());
        if (!bundleDirectory) return nil;

        NSString *assetsPath =
            [CAMLThemeRoot(theme) stringByAppendingPathComponent:@"Assets"];
        NSBundle *bundle =
            [NSBundle bundleWithPath:[assetsPath stringByAppendingPathComponent:
                                                    [NSString stringWithUTF8String:bundleDirectory]]];
        if (!bundle) return nil;
        Class descriptionClass = objc_getClass("CCUICAPackageDescription");
        if (!descriptionClass) return nil;
        // Verified initializer (ABI map §2 rows 1-3): the ORIGINAL stock package name is
        // resolved inside our rooted theme bundle; the incoming description object is never
        // mutated. Returns +1 here (ns_returns_retained contract); the non-ARC shim releases
        // it exactly once after the original invocation.
        id replacement = [[descriptionClass alloc] initWithPackageName:name inBundle:bundle];
        if (!replacement) return nil;
        // Fail open if the private initializer did not resolve a package inside our bundle.
        id replacementURL = ((id(*)(id, SEL))objc_msgSend)(replacement, @selector(packageURL));
        if (![replacementURL isKindOfClass:[NSURL class]]) return nil;
        return replacement;
    } @catch (...) {
        return nil;
    }
}

// ---- install record (called by the shim after the original setter invocation) ----

extern "C" void CAMLRecordPackageInstall(__unsafe_unretained id consumer,
                              __unsafe_unretained id stockDescription,
                              __unsafe_unretained id installedDescription,
                              bool installedOwned, int seam) {
    @try {
        if (![NSThread isMainThread]) {
            // Setters run on the main thread by contract; this hop only defends
            // that assumption. Strong locals keep the borrowed arguments alive
            // across the defer.
            id consumerStrong = consumer;
            id stock = stockDescription;
            id installed = installedDescription;
            dispatch_async(dispatch_get_main_queue(), ^{
                CAMLRecordPackageInstall(consumerStrong, stock, installed, installedOwned, seam);
            });
            return;
        }
        if (!consumer) return;
        [PackageConsumers() addObject:consumer];
        objc_setAssociatedObject(consumer, kPackageSeamKey, @(seam),
                                 OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        NSString *identifier = CAMLPackageStem(stockDescription);
        if (!identifier) return; // non-conforming stock: nothing to own or recover
        // The newest stock description always wins as the recovery original
        // (identity changes and re-assignments supersede older records); the
        // applied field distinguishes our owned replacement from untouched stock.
        id applied = installedOwned ? installedDescription : nil;
        NSNumber *appliedTheme = installedOwned ? @(PlampyCCThemeType()) : nil;
        StorePackageState(consumer, identifier, stockDescription, applied, appliedTheme);
    } @catch (...) {
        // Fail open: tracking is best effort and the stock setter already ran.
    }
}

// ---- main-thread reconcile pass ----

static void ReconcilePackageConsumer(__unsafe_unretained id consumer) {
    @try {
        NSNumber *seamNumber = objc_getAssociatedObject(consumer, kPackageSeamKey);
        if (!seamNumber) return;
        int seam = seamNumber.intValue;
        id installed = nil;
        if (!ReadInstalledDescription(consumer, &installed)) return; // fail open: no verified recovery read-back

        NSDictionary *state = objc_getAssociatedObject(consumer, kPackageOverrideKey);
        id original = state[@"original"];
        id applied = state[@"applied"];
        NSNumber *appliedTheme = state[@"appliedTheme"];
        BOOL installedIsApplied = applied != nil && SameDescription(installed, applied);
        BOOL installedIsOriginal = original != nil && SameDescription(installed, original);
        caml_replacement::InstallObservation observation = caml_replacement::ClassifyInstall(
            installed != nil, installedIsApplied, installedIsOriginal);
        if (observation == caml_replacement::InstallObservation::StockChanged) {
            // A newer stock description (assigned outside the intercepted
            // seams) is installed: adopt it as the recovery original and drop
            // ownership so restoration can never overwrite it.
            original = installed;
            applied = nil;
            appliedTheme = nil;
        }
        if (observation == caml_replacement::InstallObservation::NoDescription) {
            StorePackageState(consumer, nil, nil, nil, nil); // nothing to own or recover
            return;
        }

        NSString *identifier = CAMLPackageStem(original);
        bool sliderSite = seam == (int)caml_replacement::Seam::SliderPackage;
        // Attempting the construction is the resource-availability probe: a
        // missing or unsupported theme resource yields nil and drives the
        // restore/keep decisions below. The +1 result is released exactly once
        // by ARC at scope end when it is not installed.
        id desired = identifier ? CAMLCreateReplacementDescription(consumer, original, sliderSite) : nil;
        bool ownedThemeSatisfies =
            applied != nil && appliedTheme != nil && appliedTheme.intValue == PlampyCCThemeType();
        caml_replacement::ReconcileFacts facts = {
            PlampyCCFunctionalEnabled(), desired != nil, observation, ownedThemeSatisfies,
        };
        switch (caml_replacement::DecideReconcile(facts)) {
            case caml_replacement::ReconcileAction::KeepInstalled:
                // Preserve the installed description untouched (stock or owned).
                StorePackageState(consumer, identifier, original,
                                  installedIsApplied ? applied : nil,
                                  installedIsApplied ? appliedTheme : nil);
                break;
            case caml_replacement::ReconcileAction::ApplyReplacement:
                CAMLInvokeOriginalPackage(seam, consumer, desired);
                StorePackageState(consumer, identifier, original, desired, @(PlampyCCThemeType()));
                break;
            case caml_replacement::ReconcileAction::RestoreStock:
                // Only reachable while our applied replacement is provably
                // installed (class: OwnedReplacement), so the recorded original
                // is exactly the newest stock description to put back.
                CAMLInvokeOriginalPackage(seam, consumer, original);
                StorePackageState(consumer, nil, nil, nil, nil);
                break;
        }
    } @catch (...) {
        // Fail open per consumer: leave the installed description untouched.
    }
}

extern "C" void CAMLReconcilePackageConsumers(void) {
    if (![NSThread isMainThread]) {
        dispatch_async(dispatch_get_main_queue(), ^{ CAMLReconcilePackageConsumers(); });
        return;
    }
    for (id consumer in [PackageConsumers() allObjects]) ReconcilePackageConsumer(consumer);
}

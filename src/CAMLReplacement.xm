// Functional animated CAML replacement — verified construct-and-pass route
// with live preference reconciliation.
//
// Evidence: evidence/CAML-ABI-MAP-21D50.md (21D50, iPhone15,2), §2-§4.
// This module only ever uses the declarations in src/CAMLVerifiedABI.h: the
// package-description initializer, packageURL, and the glyphPackageDescription
// recovery read-back. The three hooked setters are invoked through their
// original-IMP slots (the shim's hook bodies and CAMLInvokeOriginalPackage)
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
//
// Owned-input classification (SP1-R1 correction): a setter input is not
// necessarily stock — a caller may re-assign a description we previously
// installed (ABI map §4 describes valid same-object setter assignments).
// Every input is classified against the recorded owned/applied state before
// construction and recording: an owned replacement is never recorded as stock
// and never replaces the preserved real-stock recovery object (that original
// survives even when reconstruction fails), while a genuinely newer stock
// description is still adopted as the recovery original. The classification
// and record/reconcile transitions live in src/CAMLReplacementCore.hpp
// (caml_replacement::ClassifyIncoming / PlanConstruction / RecordInstall /
// ObserveReconcile / PlanReconcileAction) and are the exact code exercised by
// tests/native-caml-diagnostic.cpp through injected handle boundaries; this
// module is the Objective-C adapter around them. Descriptions constructed
// here carry an owned-marker association so a stale owned replacement can
// never masquerade as "genuinely newer stock".
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
// identity key, the recovery original (newest genuine stock description seen),
// and the owned applied replacement plus the theme it was built for. All
// references are strong but bounded to the consumer's lifetime: the record is
// an associated object and the registry below is weak, so consumer destruction
// releases the record (and its original/applied references) automatically.
// (That teardown is Foundation runtime behavior: structurally relied upon
// here, not executable on a non-Darwin host and never claimed as host-tested.)
static const char kPackageOverrideKey[] = "plampy.packageOverride";
static const char kPackageSeamKey[] = "plampy.packageSeam";
// Owned-marker association: set on every description this factory constructs.
// ClassifyIncoming consults it so a stale owned replacement re-assigned after
// its record is gone can never be adopted as "genuinely newer stock".
static const char kPackageOwnedKey[] = "plampy.packageOwnedReplacement";

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

// ---- injected handle boundaries for the pure transitions ----

static caml_replacement::DescriptionHandle HandleOf(__unsafe_unretained id description) {
    return (__bridge caml_replacement::DescriptionHandle)description;
}

static id ObjectFor(caml_replacement::DescriptionHandle handle) {
    return (__bridge id)handle;
}

static bool ObjCDescriptionEqual(caml_replacement::DescriptionHandle left,
                                 caml_replacement::DescriptionHandle right) {
    return SameDescription(ObjectFor(left), ObjectFor(right)) ? true : false;
}

static bool ObjCDescriptionOwned(caml_replacement::DescriptionHandle handle) {
    if (!handle) return false;
    return objc_getAssociatedObject(ObjectFor(handle), kPackageOwnedKey) != nil;
}

static caml_replacement::RecoveryState LoadRecoveryState(__unsafe_unretained id consumer,
                                                        bool *outPresent) {
    NSDictionary *state = objc_getAssociatedObject(consumer, kPackageOverrideKey);
    if (outPresent) *outPresent = state != nil;
    caml_replacement::RecoveryState loaded = caml_replacement::NoRecoveryState();
    loaded.original = HandleOf(state[@"original"]);
    loaded.applied = HandleOf(state[@"applied"]);
    NSNumber *appliedTheme = state[@"appliedTheme"];
    loaded.appliedTheme = loaded.applied ? appliedTheme.intValue : -1;
    return loaded;
}

static void StoreRecoveryState(__unsafe_unretained id consumer,
                               const caml_replacement::RecoveryState &state) {
    id original = ObjectFor(state.original);
    id applied = ObjectFor(state.applied);
    NSString *identifier = original ? CAMLPackageStem(original) : nil;
    NSNumber *appliedTheme = applied ? @(state.appliedTheme) : nil;
    StorePackageState(consumer, identifier, original, applied, appliedTheme);
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
        // SP1-R1 classification before construction (production policy): an
        // input that is already an owned replacement is never treated as
        // stock. It is kept as-is while it is the current applied replacement
        // for this theme, and rebuilt from the preserved real stock otherwise.
        bool hasPrior = false;
        caml_replacement::RecoveryState prior = LoadRecoveryState(consumer, &hasPrior);
        caml_replacement::ConstructionPlan plan = caml_replacement::PlanConstruction(
            prior, hasPrior, HandleOf(description), PlampyCCThemeType(),
            &ObjCDescriptionEqual, &ObjCDescriptionOwned);
        if (plan.keepOwned) return nil;
        NSString *name = CAMLPackageStem(ObjectFor(plan.source));
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
        // Mark the construction as ours for good: later setter inputs that are
        // replacements we built are classified OwnedReplacement and can never
        // be recorded as stock, no matter what happens to the record.
        objc_setAssociatedObject(replacement, kPackageOwnedKey, @YES,
                                 OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        return replacement;
    } @catch (...) {
        return nil;
    }
}

// ---- install record (called by the shim after the original setter invocation) ----

extern "C" void CAMLRecordPackageInstall(__unsafe_unretained id consumer,
                              __unsafe_unretained id incomingDescription,
                              __unsafe_unretained id installedDescription,
                              bool installedOwned, int seam) {
    @try {
        if (![NSThread isMainThread]) {
            // Setters run on the main thread by contract; this hop only defends
            // that assumption. Strong locals keep the borrowed arguments alive
            // across the defer.
            id consumerStrong = consumer;
            id incoming = incomingDescription;
            id installed = installedDescription;
            dispatch_async(dispatch_get_main_queue(), ^{
                CAMLRecordPackageInstall(consumerStrong, incoming, installed, installedOwned, seam);
            });
            return;
        }
        if (!consumer) return;
        [PackageConsumers() addObject:consumer];
        objc_setAssociatedObject(consumer, kPackageSeamKey, @(seam),
                                 OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        bool hasPrior = false;
        caml_replacement::RecoveryState prior = LoadRecoveryState(consumer, &hasPrior);
        caml_replacement::DescriptionHandle incoming = HandleOf(incomingDescription);
        // SP1-R1 classification before recording (production policy): only a
        // genuinely newer stock description can become the recovery original.
        if (caml_replacement::ClassifyIncoming(prior, hasPrior, incoming, &ObjCDescriptionEqual,
                                              &ObjCDescriptionOwned) ==
            caml_replacement::IncomingKind::NewStock) {
            // Non-conforming stock has no package identity to recover or route:
            // leave any existing record untouched (fail open). An owned input
            // always records, so ownership and the preserved original survive
            // even when reconstruction missed.
            if (!CAMLPackageStem(incomingDescription)) return;
        }
        caml_replacement::InstallInput input = {
            prior, hasPrior, incoming, HandleOf(installedDescription), installedOwned,
            PlampyCCThemeType(), seam,
        };
        StoreRecoveryState(consumer, caml_replacement::RecordInstall(
                                        input, &ObjCDescriptionEqual, &ObjCDescriptionOwned));
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

        bool hasPrior = false;
        caml_replacement::RecoveryState prior = LoadRecoveryState(consumer, &hasPrior);
        caml_replacement::DescriptionHandle installedHandle = HandleOf(installed);
        // Production transitions (CAMLReplacementCore.hpp): classify the
        // read-back and adopt genuinely newer stock first, then decide with the
        // factory probe result and persist exactly the planned state. The
        // NoDescription (cleared/destroyed record) case resolves inside the
        // same planned path: no construction source, no setter invocation,
        // record cleared.
        caml_replacement::ReconcileObservation observed = caml_replacement::ObserveReconcile(
            prior, hasPrior, installedHandle, installed != nil, &ObjCDescriptionEqual);

        bool sliderSite = seam == (int)caml_replacement::Seam::SliderPackage;
        // Attempting the construction is the resource-availability probe: a
        // missing or unsupported theme resource yields nil and drives the
        // restore/keep decisions below. The construction source is always the
        // real stock description (never an owned replacement). The +1 result is
        // released exactly once by ARC at scope end when it is not installed.
        id desired = observed.constructionSource
                         ? CAMLCreateReplacementDescription(
                               consumer, ObjectFor(observed.constructionSource), sliderSite)
                         : nil;
        caml_replacement::ReconcilePlan plan = caml_replacement::PlanReconcileAction(
            observed.base, observed.kind, installedHandle, PlampyCCFunctionalEnabled(),
            HandleOf(desired), PlampyCCThemeType(), seam, &ObjCDescriptionEqual);
        if (plan.perform) CAMLInvokeOriginalPackage(seam, consumer, ObjectFor(plan.invoke));
        if (plan.clear) {
            StorePackageState(consumer, nil, nil, nil, nil);
        } else {
            StoreRecoveryState(consumer, plan.next);
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

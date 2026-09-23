// Replacement IMP shim for the six CAML diagnostic sites.
//
// Compiled with ARC disabled (see the Makefile): this file owns the ABI edge —
// borrowed hook arguments, original-IMP invocation, and exactly-one release of
// the factory's +1 replacement. ARC Objective-C work lives in
// src/CAMLDiagnostic.xm and src/CAMLReplacement.xm.
//
// Per-hook contract (ABI map §4): guard-only admission first; observe the
// borrow; construct-or-pass (+1 replacement or the borrowed description);
// invoke the original IMP exactly once with that single argument (retain-first
// setter storage, never an unretained arg); record the owned/applied recovery
// state; release the +1 replacement exactly once; never release the incoming
// description.

#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <substrate.h>
#import "CAMLDiagnostic.h"
#import "CAMLReplacement.h"

#if __has_feature(objc_arc)
#error "must be compiled with ARC disabled"
#endif

// Original-IMP slots written by the diagnostic installer (the descriptor table
// in src/CAMLDiagnostic.xm passes &gOriginal*). C linkage matches that
// translation unit's `extern "C"` declarations; these ARE the definitions.
extern "C" {
IMP gOriginalButtonPackage = NULL;
IMP gOriginalRoundPackage = NULL;
IMP gOriginalSliderPackage = NULL;
IMP gOriginalFactory = NULL;
IMP gOriginalButtonState = NULL;
IMP gOriginalSliderState = NULL;
}

extern "C" void ObservePackage(__unsafe_unretained id view, __unsafe_unretained id description, const char *site);
extern "C" void ObserveState(__unsafe_unretained id view, __unsafe_unretained id state, const char *site);
extern "C" void ObserveFactory(__unsafe_unretained id packageName);

// MRR release of the construction boundary's +1 result. The message-send
// release form is the source form guaranteed valid in a non-ARC
// Objective-C++ translation unit under the pinned SDK: it depends neither on
// a direct runtime release entry-point declaration (whose SDK availability is
// unverified) nor on ARC, while preserving exactly-one release semantics.
// Exactly one call site per package hook, after the original invocation and
// the recovery-state record; the borrowed incoming description is never
// released here.
extern "C" __attribute__((noinline, used)) void CAMLReleaseReplacement(__unsafe_unretained id replacement) {
    [replacement release];
}

// Reconcile-time invocation of the seam's original setter IMP (ABI map §2
// rows 1-3). Direct original-slot dispatch — never the intercepted hook — so
// restoration cannot re-enter the replacement path or overwrite
// original-description recovery state. The selector name is the verified
// string; SEL identity matches the intercepted cmd by uniquing.
extern "C" __attribute__((noinline, used)) void CAMLInvokeOriginalPackage(int seam, __unsafe_unretained id consumer,
                                                                         __unsafe_unretained id description) {
    IMP original = seam == 0 ? gOriginalButtonPackage
                             : (seam == 1 ? gOriginalRoundPackage : gOriginalSliderPackage);
    if (original) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))original)(consumer, sel_registerName("setGlyphPackageDescription:"), description);
}

extern "C" __attribute__((noinline, used)) void CAMLButtonPackageHook(__unsafe_unretained id self, SEL cmd,
                                                            __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "button-view");
    __unsafe_unretained id replacement = CAMLCreateReplacementDescription(self, description, false);
    __unsafe_unretained id argument = replacement ? replacement : description;
    if (gOriginalButtonPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalButtonPackage)(self, cmd, argument);
    CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 0);
    if (replacement) CAMLReleaseReplacement(replacement);
}

extern "C" __attribute__((noinline, used)) void CAMLRoundPackageHook(__unsafe_unretained id self, SEL cmd,
                                                           __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "round-button");
    __unsafe_unretained id replacement = CAMLCreateReplacementDescription(self, description, false);
    __unsafe_unretained id argument = replacement ? replacement : description;
    if (gOriginalRoundPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalRoundPackage)(self, cmd, argument);
    CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 1);
    if (replacement) CAMLReleaseReplacement(replacement);
}

extern "C" __attribute__((noinline, used)) void CAMLSliderPackageHook(__unsafe_unretained id self, SEL cmd,
                                                            __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "slider-view");
    __unsafe_unretained id replacement = CAMLCreateReplacementDescription(self, description, true);
    __unsafe_unretained id argument = replacement ? replacement : description;
    if (gOriginalSliderPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalSliderPackage)(self, cmd, argument);
    CAMLRecordPackageInstall(self, description, argument, replacement != NULL, 2);
    if (replacement) CAMLReleaseReplacement(replacement);
}

extern "C" __attribute__((noinline, used)) id CAMLFactoryHook(__unsafe_unretained id self, SEL cmd,
                                                      __unsafe_unretained id packageName,
                                                      __unsafe_unretained id bundle) {
    if (CAMLDiagnosticPrimitiveAdmission(true)) ObserveFactory(packageName);
    return gOriginalFactory ? ((id(*)(__unsafe_unretained id, SEL, __unsafe_unretained id, __unsafe_unretained id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;
}

extern "C" __attribute__((noinline, used)) void CAMLButtonStateHook(__unsafe_unretained id self, SEL cmd,
                                                          __unsafe_unretained id state) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObserveState(self, state, "glyph-state");
    if (gOriginalButtonState) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalButtonState)(self, cmd, state);
}

extern "C" __attribute__((noinline, used)) void CAMLSliderStateHook(__unsafe_unretained id self, SEL cmd,
                                                          __unsafe_unretained id state) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObserveState(self, state, "glyph-state");
    if (gOriginalSliderState) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalSliderState)(self, cmd, state);
}

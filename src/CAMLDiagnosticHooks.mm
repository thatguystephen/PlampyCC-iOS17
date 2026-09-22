#if __has_feature(objc_arc)
#error "CAMLDiagnosticHooks.mm must be compiled with ARC disabled"
#endif

// Replacement IMPs are intentionally isolated from ARC.  Every object is a
// borrowed argument for the synchronous observer call; no ownership operation
// may occur before CAMLDiagnosticPrimitiveAdmission returns true.
#import <objc/runtime.h>
#import <substrate.h>
#import "CAMLDiagnostic.h"

IMP gOriginalButtonPackage = NULL;
IMP gOriginalRoundPackage = NULL;
IMP gOriginalSliderPackage = NULL;
IMP gOriginalFactory = NULL;
IMP gOriginalButtonState = NULL;
IMP gOriginalSliderState = NULL;

__attribute__((noinline, used)) void CAMLButtonPackageHook(__unsafe_unretained id self, SEL cmd,
                                                            __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "button-view");
    if (gOriginalButtonPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalButtonPackage)(self, cmd, description);
}

__attribute__((noinline, used)) void CAMLRoundPackageHook(__unsafe_unretained id self, SEL cmd,
                                                           __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "round-button");
    if (gOriginalRoundPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalRoundPackage)(self, cmd, description);
}

__attribute__((noinline, used)) void CAMLSliderPackageHook(__unsafe_unretained id self, SEL cmd,
                                                            __unsafe_unretained id description) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObservePackage(self, description, "slider-view");
    if (gOriginalSliderPackage) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalSliderPackage)(self, cmd, description);
}

__attribute__((noinline, used)) id CAMLFactoryHook(__unsafe_unretained id self, SEL cmd,
                                                    __unsafe_unretained id packageName,
                                                    __unsafe_unretained id bundle) {
    if (CAMLDiagnosticPrimitiveAdmission(true)) ObserveFactory(packageName);
    // The original is deliberately outside the diagnostic boundary and is
    // invoked once with the exact arguments and returned without rewriting.
    return gOriginalFactory ? ((id(*)(__unsafe_unretained id, SEL, __unsafe_unretained id, __unsafe_unretained id))gOriginalFactory)(self, cmd, packageName, bundle) : nil;
}

__attribute__((noinline, used)) void CAMLButtonStateHook(__unsafe_unretained id self, SEL cmd,
                                                         __unsafe_unretained id state) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObserveState(self, state, "glyph-state");
    if (gOriginalButtonState) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalButtonState)(self, cmd, state);
}

__attribute__((noinline, used)) void CAMLSliderStateHook(__unsafe_unretained id self, SEL cmd,
                                                         __unsafe_unretained id state) {
    if (CAMLDiagnosticPrimitiveAdmission(false)) ObserveState(self, state, "glyph-state");
    if (gOriginalSliderState) ((void(*)(__unsafe_unretained id, SEL, __unsafe_unretained id))gOriginalSliderState)(self, cmd, state);
}

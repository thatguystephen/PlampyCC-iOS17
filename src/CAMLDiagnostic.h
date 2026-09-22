#ifndef PLAMPYCC_CAML_DIAGNOSTIC_H
#define PLAMPYCC_CAML_DIAGNOSTIC_H

#ifdef __cplusplus
extern "C" {
#endif

// Flushes the bounded diagnostic ring at the existing Control Center dismissal seam.
// It is a no-op unless diagnostics are enabled and a ring flush is pending.
void CAMLDiagnosticFlushAtDismiss(void);

// POD-only admission used by the non-ARC replacement IMP translation unit.
// It must remain free of Objective-C messages, ownership operations, allocation,
// logging, and filesystem work.
#ifdef __cplusplus
bool CAMLDiagnosticPrimitiveAdmission(bool verboseOnly);
#endif

#ifdef __OBJC__
#define CAML_DIAGNOSTIC_BORROWED __unsafe_unretained
void ObservePackage(CAML_DIAGNOSTIC_BORROWED id view,
                    CAML_DIAGNOSTIC_BORROWED id description,
                    const char *site);
void ObserveState(CAML_DIAGNOSTIC_BORROWED id view,
                  CAML_DIAGNOSTIC_BORROWED id state,
                  const char *site);
void ObserveFactory(CAML_DIAGNOSTIC_BORROWED id packageName);
#undef CAML_DIAGNOSTIC_BORROWED
#endif

#ifdef __cplusplus
}
#endif

#endif

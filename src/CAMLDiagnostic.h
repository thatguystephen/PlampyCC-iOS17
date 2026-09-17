#ifndef PLAMPYCC_CAML_DIAGNOSTIC_H
#define PLAMPYCC_CAML_DIAGNOSTIC_H

#ifdef __cplusplus
extern "C" {
#endif

// Flushes the bounded diagnostic ring at the existing Control Center dismissal seam.
// It is a no-op unless diagnostics are enabled and a ring flush is pending.
void CAMLDiagnosticFlushAtDismiss(void);

#ifdef __cplusplus
}
#endif

#endif

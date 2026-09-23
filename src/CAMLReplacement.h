#ifndef PLAMPYCC_CAML_REPLACEMENT_H
#define PLAMPYCC_CAML_REPLACEMENT_H

// Live animated CAML replacement boundary — verified 21D50 construct-and-pass
// route (evidence/CAML-ABI-MAP-21D50.md §3-§4) with live preference
// reconciliation. The construction, ownership-record, and reconciliation
// implementations live in the ARC translation unit src/CAMLReplacement.xm. The
// non-ARC hook shim src/CAMLDiagnosticHooks.mm calls the construction and
// record boundaries and implements the original-IMP invocation and the single
// MRR release helper.
//
// Ownership contract:
// - CAMLCreateReplacementDescription returns either nil (fail open: the stock
//   description passes through untouched) or a +1 replacement that must be
//   released exactly once after the original setter invocation (MRR
//   CAMLReleaseReplacement in the shim; ARC scope-end inside the reconcile
//   pass). It classifies the input first: an already-owned replacement is
//   never treated as stock (it is kept as-is while current, or rebuilt from
//   the preserved real-stock original), and every constructed replacement
//   carries the owned-marker association.
// - The borrowed incoming description is never released or mutated; no
//   private URL ivar is ever read or written.
// - CAMLRecordPackageInstall copies (retains) what it needs synchronously
//   before returning, so the shim may release the replacement immediately
//   afterwards even when the record hop defers to the main thread. The
//   `incomingDescription` is whatever the caller passed to the setter — stock
//   OR one of our own owned replacements — and is classified against the
//   recorded owned/applied state before recording; only genuinely newer stock
//   is adopted as the recovery original.
#ifdef __OBJC__

// C linkage on every boundary entry point: the definitions in
// src/CAMLReplacement.xm and src/CAMLDiagnosticHooks.mm are declared
// `extern "C"`, and a C++-linkage declaration followed by an `extern "C"`
// definition is an ill-formed conflicting-language-linkage error.
#ifdef __cplusplus
extern "C" {
#endif

// +1 replacement or nil. `consumer` must support the verified
// glyphPackageDescription recovery read-back; otherwise this fails open so an
// unrecoverable override is never installed. `description` is the borrowed
// setter input (genuine stock or one of our own owned replacements) used to
// derive the package name — from the preserved real-stock original when the
// input is already owned.
id CAMLCreateReplacementDescription(__unsafe_unretained id consumer,
                                    __unsafe_unretained id description,
                                    bool sliderSite)
    __attribute__((ns_returns_retained));

// Called by the shim exactly once after the original setter invocation with
// the borrowed incoming description (stock or an owned replacement being
// re-assigned), the object actually installed (the replacement or the input
// description itself), and whether that object is a freshly constructed owned
// replacement. Records the classified stock/applied distinction in the weak
// consumer registry for later main-thread reconciliation: the preserved real
// stock original survives owned re-assignments (even failed reconstruction),
// and ownership is dropped only when genuine stock actually replaces our
// replacement. Seam is caml_replacement::Seam's integer value.
void CAMLRecordPackageInstall(__unsafe_unretained id consumer,
                              __unsafe_unretained id incomingDescription,
                              __unsafe_unretained id installedDescription,
                              bool installedOwned, int seam);

// Main-thread reconciliation pass over the weak consumer registry. Handles
// disabled-start->enable, Plampy<->Pulsar theme changes, disable/re-enable,
// missing or unsupported resources, and newer stock assignments (adopted,
// never overwritten). Consumers destroyed since the last pass are absent from
// the weak registry and skipped. Fails open per consumer.
void CAMLReconcilePackageConsumers(void);

// Shim-side: invoke the seam's original setGlyphPackageDescription: IMP
// directly (never through the intercepted hook) so reconciliation never
// re-enters the replacement path or overwrites original-description recovery
// state.
void CAMLInvokeOriginalPackage(int seam, __unsafe_unretained id consumer,
                               __unsafe_unretained id description);

// Shim-side MRR release of the factory's +1 result. Exactly one call site per
// package hook, after the original invocation and after CAMLRecordPackageInstall.
void CAMLReleaseReplacement(__unsafe_unretained id replacement);

#ifdef __cplusplus
}
#endif

#endif /* __OBJC__ */
#endif /* PLAMPYCC_CAML_REPLACEMENT_H */

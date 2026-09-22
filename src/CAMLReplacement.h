#ifndef PLAMPYCC_CAML_REPLACEMENT_H
#define PLAMPYCC_CAML_REPLACEMENT_H

// Functional animated CAML replacement boundary (verified construct-and-pass
// route, evidence/CAML-ABI-MAP-21D50.md §3-§4). The implementation lives in
// the ARC translation unit src/CAMLReplacement.xm; the non-ARC hook shim in
// src/CAMLDiagnosticHooks.mm is the only caller.
#ifdef __cplusplus
extern "C" {
#endif

#ifdef __OBJC__
// Returns a +1 (ns_returns_retained) replacement CCUICAPackageDescription
// built from the theme bundle, or nil for fail-open pass-through of the
// original description. sliderSite selects the verified slider route
// (containsString: dispatch) instead of the exact-name map route.
//
// Ownership contract (ABI map §4): the caller passes the result to the
// original setter (which retains it, verified retain-first) and then releases
// it exactly once. The incoming description's ownership is never touched.
id CAMLCreateReplacementDescription(__unsafe_unretained id description, bool sliderSite)
    __attribute__((ns_returns_retained));
#endif

#ifdef __cplusplus
}
#endif

#endif

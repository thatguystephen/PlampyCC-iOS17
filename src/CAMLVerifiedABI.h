#ifndef PLAMPYCC_CAML_VERIFIED_ABI_H
#define PLAMPYCC_CAML_VERIFIED_ABI_H

// Declarations reconstructed from machine-level-verified 21D50 evidence
// (evidence/CAML-ABI-MAP-21D50.md §2 rows 4 and 6). These are the only
// private ControlCenterUIKit entry points the functional CAML route uses:
//
//   -[CCUICAPackageDescription initWithPackageName:inBundle:]
//       21D50 impl 0x1d308a228, encoding @24@0:8@16@24 (init convention),
//       resolves URLForResource:withExtension: inside the given bundle and
//       stores the URL at ivar +0x18. Returns retained self.
//   -[CCUICAPackageDescription packageURL]
//       21D50 impl 0x1d308a360, encoding @16@0:8, ivar-backed.
//
// No other private selector, ivar, or call-site ABI is assumed. The three
// hooked setters are reached through their verified original-IMP slots, not
// through re-declared selectors.
#import <Foundation/Foundation.h>

@interface NSObject (CAMLVerifiedPackageDescription)
- (id)initWithPackageName:(NSString *)packageName inBundle:(NSBundle *)bundle;
- (NSURL *)packageURL;
// Recovery read-back only: used to compare the currently installed description
// against the recorded original/applied pair before installing or restoring
// anything (never mutated). Selector existence machine-verified in the 21D50
// selector table (evidence/CAML-ABI-MAP-21D50.md §7.1); storage verified as the
// _glyphPackageDescription ivar the setters write (§2). Called only behind a
// respondsToSelector check so a miss fails open.
- (id)glyphPackageDescription;
@end

#endif

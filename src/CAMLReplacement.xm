// Functional animated CAML replacement — verified construct-and-pass route.
//
// Evidence: evidence/CAML-ABI-MAP-21D50.md (21D50, iPhone15,2), §2-§4.
// This module only ever uses the machine-verified declarations in
// src/CAMLVerifiedABI.h: the package-description initializer and packageURL.
// The three hooked setters are invoked through their original-IMP slots by
// the non-ARC shim, never through re-declared selectors here.
//
// Route (ABI map §3): build "<theme root>/Assets/<mapped bundle>" from the
// rooted theme directory, construct a fresh CCUICAPackageDescription with the
// ORIGINAL package name and that bundle, and hand it to the stock setter.
// Every miss (disabled tweak, non-conforming description, unmapped name,
// timer under Pulsar, bundle/initializer failure, nil resolved packageURL,
// any exception) fails open: the shim forwards the original description
// unchanged. No runtime animation claim is made by this implementation; the
// five deferred runtime observations are listed in docs/CAML-REPLACEMENT-IMPLEMENTATION.md.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <rootless.h>
#import "CAMLReplacement.h"
#import "CAMLVerifiedABI.h"
#import "PlampyCCState.h"
#include "CAMLReplacementCore.hpp"

// The rooted theme directory; mirrors src/Tweak.xm ThemeRoot() exactly (the
// logical runtime root is /var/mobile/Library/Application Support/PlampyCC and
// ROOT_PATH_NS supplies the single rootless prefix at runtime).
static NSString *CAMLThemeRoot(void) {
    NSString *root = ROOT_PATH_NS(@"/var/mobile/Library/Application Support/PlampyCC");
    return [root stringByAppendingPathComponent:PlampyCCThemeType() == 1 ? @"Pulsar" : @"Plampy"];
}

// Verified identity rule (ABI map §1.7): module identity is the filename stem
// of the incoming description's packageURL. Returns nil unless the description
// conforms.
static NSString *CAMLPackageStem(id description) {
    if (![description respondsToSelector:@selector(packageURL)]) return nil;
    id packageURL = [description packageURL];
    if (![packageURL isKindOfClass:[NSURL class]]) return nil;
    NSString *path = [(NSURL *)packageURL path];
    NSString *stem = [[path lastPathComponent] stringByDeletingPathExtension];
    return stem.length > 0 ? stem : nil;
}

extern "C" id CAMLCreateReplacementDescription(__unsafe_unretained id description, bool sliderSite)
    __attribute__((ns_returns_retained)) {
    @try {
        if (!description || !PlampyCCFunctionalEnabled()) return nil;
        NSString *name = CAMLPackageStem(description);
        if (!name) return nil;
        const char *bundleDirectory = caml_replacement::BundleDirectoryForPackage(
            std::string_view([name UTF8String]),
            sliderSite ? caml_replacement::Site::Slider : caml_replacement::Site::Setter,
            PlampyCCThemeType());
        if (!bundleDirectory) return nil;
        NSString *bundlePath = [NSString stringWithFormat:@"%@/Assets/%s", CAMLThemeRoot(), bundleDirectory];
        NSBundle *bundle = [NSBundle bundleWithPath:bundlePath];
        if (!bundle) return nil;
        Class descriptionClass = NSClassFromString(@"CCUICAPackageDescription");
        if (!descriptionClass) return nil;
        id replacement = [[descriptionClass alloc] initWithPackageName:name inBundle:bundle];
        if (!replacement) return nil;
        // Fail open unless the verified initializer resolved a resource URL
        // (ABI map §3: a bad replacement path must degrade to the stock
        // description, never to a blank glyph).
        id replacementURL = [replacement respondsToSelector:@selector(packageURL)] ? [replacement packageURL] : nil;
        if (![replacementURL isKindOfClass:[NSURL class]]) return nil;
        return replacement; // +1 per ns_returns_retained; the shim releases once
    } @catch (...) {
        return nil;
    }
}

// Host-side native gate for an EXTENDED generated theme catalog (M0 existing-
// family-extension fixture). Compiled and run by tests/theme-catalog-validation.ts
// against a scratch-rendered header, with the extended census counts supplied as
// compile-time macros. It proves the extended header compiles and runs — the
// exact static_asserts in the generated header already pin the extended
// contract at compile time; this probe additionally inspects every entry and
// every module -> capability ownership edge under the extended census.
#include "PlampyCCThemeCatalog.hpp"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>

#ifndef EXPECT_MODULE_COUNT
#error "EXPECT_MODULE_COUNT must be defined"
#endif
#ifndef EXPECT_CAPABILITY_COUNT
#error "EXPECT_CAPABILITY_COUNT must be defined"
#endif
#ifndef EXPECT_ELIGIBLE_COUNT
#error "EXPECT_ELIGIBLE_COUNT must be defined"
#endif
#ifndef EXPECT_ACTIVE_BITS
#error "EXPECT_ACTIVE_BITS must be defined"
#endif

using namespace plampycc::generated;

static std::uint32_t Fnv1a32(const char *input) {
    std::uint32_t hash = 0x811c9dc5u;
    for (const char *p = input; *p != '\0'; ++p) {
        hash ^= static_cast<unsigned char>(*p);
        hash *= 0x01000193u;
    }
    return hash;
}

int main() {
    assert(kModuleCount == EXPECT_MODULE_COUNT);
    assert(kCapabilityCount == EXPECT_CAPABILITY_COUNT);
    assert(kEligibleCount == EXPECT_ELIGIBLE_COUNT);
    assert(kStockOnlyCount == EXPECT_CAPABILITY_COUNT - EXPECT_ELIGIBLE_COUNT);
    assert(kActiveCapabilityBits == EXPECT_ACTIVE_BITS);

    for (std::size_t i = 0; i < kModuleCount; ++i) {
        const ModuleEntry &entry = kModules[i];
        assert(static_cast<std::size_t>(entry.id) == i);
        assert(entry.idString != nullptr && entry.idString[0] != '\0');
        assert(entry.safeDefault != nullptr && std::strcmp(entry.safeDefault, "stock") == 0);
        assert(entry.capabilities != nullptr && entry.capabilityCount > 0);
        for (std::size_t c = 0; c < entry.capabilityCount; ++c) {
            assert(static_cast<std::size_t>(entry.capabilities[c]) < kCapabilityCount);
        }
    }

    std::uint64_t owned = 0ull;
    for (std::size_t i = 0; i < kModuleCount; ++i) {
        for (std::size_t c = 0; c < kModules[i].capabilityCount; ++c) {
            const std::size_t ordinal = static_cast<std::size_t>(kModules[i].capabilities[c]);
            assert(!(owned & (1ull << ordinal)));
            owned |= (1ull << ordinal);
            assert(kCapabilities[ordinal].module == kModules[i].id);
        }
    }
    assert(owned == (1ull << kCapabilityCount) - 1u);

    for (std::size_t i = 0; i < kCapabilityCount; ++i) {
        const CapabilityEntry &entry = kCapabilities[i];
        assert(static_cast<std::size_t>(entry.id) == i);
        assert(entry.idString != nullptr && entry.idString[0] != '\0');
        assert(entry.tag == Fnv1a32(entry.idString));
        assert(entry.visibleStateCount > 0 && entry.visibleStates != nullptr);
        if (entry.eligible) {
            assert(entry.rendererFamily != nullptr &&
                   std::strcmp(entry.rendererFamily, "caml-package-setter") == 0);
            assert(entry.routeCount > 0 && entry.routes != nullptr);
            assert(entry.aliasCount > 0 && entry.aliases != nullptr);
        } else {
            assert(entry.rendererFamily == nullptr);
            assert(entry.routeCount == 0 && entry.routes == nullptr);
        }
    }

    assert(std::strncmp(kCatalogDigest, "sha256:", 7) == 0);
    assert(std::strncmp(kActivationSetDigest, "sha256:", 7) == 0);

    std::printf("PASS: extended native theme catalog (%zu modules, %zu capabilities, %zu eligible)\n",
                static_cast<std::size_t>(kModuleCount),
                static_cast<std::size_t>(kCapabilityCount),
                static_cast<std::size_t>(kEligibleCount));
    return 0;
}
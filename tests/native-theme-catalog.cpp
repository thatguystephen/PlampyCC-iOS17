// Host-side native gate for the generated immutable theme catalog (M0).
// Compiled and run by tests/theme-catalog-generation.ts with
// `g++ -std=c++17 -Wall -Wextra -Werror`. No Objective-C runtime is required:
// the generated header is constant C++17 data.
#include "../src/generated/PlampyCCThemeCatalog.hpp"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>

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
    // Compile-time census and length gates already ran via static_assert in the
    // header. Pin the canonical census here for the host gate on all 30
    // module identities AND the immutable Module record table.
    static_assert(kModuleCount == 30, "30 module identities required");
    static_assert(kCapabilityCount == 32, "32 capabilities required");
    static_assert(kEligibleCount == 13, "13 eligible CAML routes required");
    static_assert(kStockOnlyCount == 19, "19 stock-only dispositions required");

    // ---- immutable Module records: every identity, safe default, and
    // explicit capability-ownership edge is inspected. ----
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

    // Every capability appears in exactly one module's ownership set, and each
    // edge back-references its owning Module record.
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

        // Array position is the typed CapabilityId ordinal (constant-time lookup).
        assert(static_cast<std::size_t>(entry.id) == i);
        assert(entry.idString != nullptr && entry.idString[0] != '\0');
        assert(entry.tag == Fnv1a32(entry.idString));
        assert(entry.activeBit == 0u);  // Q0 activation set is empty

        if (entry.eligible && entry.rendererFamily != nullptr) {
            assert(std::strcmp(entry.rendererFamily, "caml-package-setter") == 0);
            assert(entry.routeCount > 0 && entry.routes != nullptr);
            assert(entry.aliasCount > 0 && entry.aliases != nullptr);
        } else {
            assert(!entry.eligible);
            assert(entry.rendererFamily == nullptr);
            assert(entry.routeCount == 0 && entry.routes == nullptr);
        }
        assert(entry.visibleStateCount > 0 && entry.visibleStates != nullptr);
    }

    // Precomputed tags are unique across the catalog.
    for (std::size_t i = 0; i < kCapabilityCount; ++i) {
        for (std::size_t j = i + 1; j < kCapabilityCount; ++j) {
            assert(kCapabilities[i].tag != kCapabilities[j].tag);
        }
    }

    // kTagIndex is a sorted index (ascending tag); it is not a constant-time
    // lookup table — constant-time lookup is the typed CapabilityId ordinal.
    std::uint64_t coverage = 0ull;
    std::uint32_t previous = 0u;
    for (std::size_t i = 0; i < kCapabilityCount; ++i) {
        const std::size_t ordinal = static_cast<std::size_t>(kTagIndex[i]);
        assert(ordinal < kCapabilityCount);
        const std::uint32_t tag = kCapabilities[ordinal].tag;
        assert(i == 0 || tag > previous);
        previous = tag;
        assert(!(coverage & (1ull << ordinal)));
        coverage |= (1ull << ordinal);
    }
    assert(coverage == (1ull << kCapabilityCount) - 1u);

    assert(std::strncmp(kCatalogDigest, "sha256:", 7) == 0);
    assert(std::strncmp(kActivationSetDigest, "sha256:", 7) == 0);
    assert(kActiveCapabilityBits == 0u);
    assert(std::strcmp(kSelectedStage, "Q0") == 0);
    assert(std::strcmp(kTargetProductType, "iPhone15,2") == 0);
    assert(std::strcmp(kTargetProductVersion, "17.3") == 0);
    assert(std::strcmp(kTargetBuild, "21D50") == 0);

    std::printf("PASS: native theme catalog (30 module records inspected, 32 capabilities, 13 eligible, 19 stock-only, Q0 empty; unique tags; constant-time ID lookup; every module->capability ownership edge verified; exact target)\n");
    return 0;
}
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
    // header. Runtime gates exercise the emitted table inline.
    static_assert(kStockOnlyCount == 19, "19 stock-only records required");

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

    // kTagIndex is a full permutation indexed by ascending tag.
    std::uint32_t coverage = 0u;
    std::uint32_t previous = 0u;
    for (std::size_t i = 0; i < kCapabilityCount; ++i) {
        const std::size_t ordinal = static_cast<std::size_t>(kTagIndex[i]);
        assert(ordinal < kCapabilityCount);
        const std::uint32_t tag = kCapabilities[ordinal].tag;
        assert(i == 0 || tag > previous);
        previous = tag;
        coverage |= (1u << ordinal);
    }
    assert(coverage == static_cast<std::uint32_t>((1ull << kCapabilityCount) - 1u));

    assert(std::strncmp(kCatalogDigest, "sha256:", 7) == 0);
    assert(std::strncmp(kActivationSetDigest, "sha256:", 7) == 0);
    assert(kActiveCapabilityBits == 0u);
    assert(std::strcmp(kSelectedStage, "Q0") == 0);
    assert(std::strcmp(kTargetProductType, "iPhone15,2") == 0);
    assert(std::strcmp(kTargetProductVersion, "17.3") == 0);
    assert(std::strcmp(kTargetBuild, "21D50") == 0);

    std::printf("PASS: native theme catalog (30 modules, 32 capabilities, 13 eligible, 19 stock-only, Q0 empty; unique tags; constant-time ID lookup; exact target)\n");
    return 0;
}
#include "../src/FlashlightOpticalPolicy.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <initializer_list>

int main() {
    using namespace flashlight_optical;
    const auto within = [](double scale) {
        return scale >= kMinimumScale && scale <= kMaximumScale;
    };
    assert(within(kCompactScale));
    assert(!within(1.0)); // d0e77a9 geometric equality is optically too small.
    assert(!within(80.0 / 25.0)); // raw canvas vs historical fallback width.
    assert(!within(144.0 / 48.0)); // raw canvas vs historical fallback height.
    assert(std::abs(52.0 * kCompactScale - 79.0) < 1e-9);
    // Model the setter -> reconciliation -> hooked setter feedback path.
    // Every generated image retains the unscaled source canvas; repeated
    // conversions therefore use the same key, even across cache invalidation.
    struct Image { double width; double sourceWidth; bool tagged; };
    const auto render = [](Image peer) {
        double base = peer.tagged ? peer.sourceWidth : peer.width;
        return Image{base * kCompactScale, base, true};
    };
    for (double width : {15.0, 25.0, 30.0}) {
        Image current{width, 0.0, false};
        for (int pass = 0; pass < 100; ++pass) {
            current = render(render(current)); // reconcile, then setter hook
            assert(std::abs(current.width / width - kCompactScale) < 1e-9);
            // A new render (as after cache invalidation) still uses the tag.
            Image afterInvalidation = render(current);
            assert(afterInvalidation.width == current.width);
        }
        Image lostMetadata{current.width, 0.0, false};
        assert(!within(render(lostMetadata).width / width));
    }
    std::printf("PASS: native scale %.9f, bounds [%.9f, %.9f]; predicted compact bbox %.3fx79; extremes rejected; feedback model stable\n",
                kCompactScale, kMinimumScale, kMaximumScale, 35.0 * kCompactScale);
}

#pragma once

namespace flashlight_optical {
// IMG_1095.JPG: median peer longest extent / compact flashlight height.
// See docs/FLASHLIGHT-OPTICAL-SIZING.md. This is NOT a header calibration.
constexpr double kCompactScale = 79.0 / 52.0;
constexpr double kMinimumScale = 73.0 / 53.0;
constexpr double kMaximumScale = 80.0 / 51.0;
static_assert(kCompactScale >= kMinimumScale && kCompactScale <= kMaximumScale,
              "Compact optical scale must remain within the measured envelope");
} // namespace flashlight_optical

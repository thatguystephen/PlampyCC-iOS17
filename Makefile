ARCHS = arm64 arm64e
TARGET = iphone:clang:16.5:15.0
THEOS_PACKAGE_SCHEME = rootless
INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = PlampyCC
PlampyCC_FILES = src/Tweak.xm src/CAMLDiagnostic.xm src/CAMLDiagnosticHooks.mm
PlampyCC_CFLAGS = -fobjc-arc -std=c++17 -Werror=return-type
# The hook ABI is a borrowed-argument boundary. Keep the six replacement IMPs
# in a dedicated translation unit and make ARC failure a compile-time error.
PlampyCC_CFLAGS_src/CAMLDiagnosticHooks.mm = -fno-objc-arc -std=c++17
PlampyCC_FRAMEWORKS = UIKit
PlampyCC_PRIVATE_FRAMEWORKS = ControlCenterUI ControlCenterUIKit
PlampyCC_LIBRARIES = substrate
PlampyCC_EXTRA_FILES = layout

include $(THEOS_MAKE_PATH)/tweak.mk

SUBPROJECTS += prefs
include $(THEOS_MAKE_PATH)/aggregate.mk

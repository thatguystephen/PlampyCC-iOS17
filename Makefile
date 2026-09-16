ARCHS = arm64 arm64e
TARGET = iphone:clang:16.5:15.0
THEOS_PACKAGE_SCHEME = rootless
INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = PlampyCC
PlampyCC_FILES = src/Tweak.xm
PlampyCC_CFLAGS = -fobjc-arc -Werror=return-type
PlampyCC_FRAMEWORKS = UIKit
PlampyCC_PRIVATE_FRAMEWORKS = ControlCenterUI ControlCenterUIKit
PlampyCC_LIBRARIES = substrate
PlampyCC_EXTRA_FILES = layout

include $(THEOS_MAKE_PATH)/tweak.mk

SUBPROJECTS += prefs
include $(THEOS_MAKE_PATH)/aggregate.mk

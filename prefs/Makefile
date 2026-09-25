include $(THEOS)/makefiles/common.mk

BUNDLE_NAME = PlampyCC
PlampyCC_FILES = RootListController.m
# RootListController.m is ARC-authored (no retain/release anywhere; bridged
# CF casts; alloc/init results are never released by hand). Theos defaults to
# MRC, where the loadSpecifiersFromPlistName: autoreleased result assigned to
# _specifiers would dangle after the autorelease pool drains and crash
# Preferences with unrecognized-selector SIGABRTs. Keep this translation unit
# explicitly ARC like the tweak's ARC TUs. Regression contract:
# tests/prefs-arc-contract.py.
PlampyCC_CFLAGS = -fobjc-arc
PlampyCC_INSTALL_PATH = /Library/PreferenceBundles
PlampyCC_FRAMEWORKS = UIKit
PlampyCC_PRIVATE_FRAMEWORKS = Preferences
include $(THEOS_MAKE_PATH)/bundle.mk

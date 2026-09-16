#import <UIKit/UIKit.h>
#import <Preferences/PSListController.h>
#import <Preferences/PSSpecifier.h>

static NSString * const kPrefsDomain = @"com.misakaproject.plampyCC";
static NSString * const kPrefsChanged = @"com.misakaproject.plampyCC.settingsChanged";

@interface PlampyCCRootListController : PSListController
@end

@implementation PlampyCCRootListController

- (NSArray *)specifiers {
    if (!_specifiers) _specifiers = [self loadSpecifiersFromPlistName:@"Root" target:self];
    return _specifiers;
}

- (id)readPreferenceValue:(PSSpecifier *)specifier {
    NSDictionary *defaults = [specifier propertyForKey:@"default"] ? @{ [specifier propertyForKey:@"key"] : [specifier propertyForKey:@"default"] } : nil;
    NSUserDefaults *preferences = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    id value = [preferences objectForKey:[specifier propertyForKey:@"key"]];
    return value ?: defaults[[specifier propertyForKey:@"key"]];
}

- (void)setPreferenceValue:(id)value specifier:(PSSpecifier *)specifier {
    NSUserDefaults *preferences = [[NSUserDefaults alloc] initWithSuiteName:kPrefsDomain];
    NSString *key = [specifier propertyForKey:@"key"];
    if (value) [preferences setObject:value forKey:key]; else [preferences removeObjectForKey:key];
    [preferences synchronize];
    CFNotificationCenterPostNotification(CFNotificationCenterGetDarwinNotifyCenter(), (__bridge CFNotificationName)kPrefsChanged, NULL, NULL, true);
    [super setPreferenceValue:value specifier:specifier];
}

@end

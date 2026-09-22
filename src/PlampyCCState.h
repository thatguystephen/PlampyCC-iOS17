#ifndef PLAMPYCC_STATE_H
#define PLAMPYCC_STATE_H

// Read-only access to the functional preference state owned by the single
// prefs boundary in src/Tweak.xm (ReloadPrefs). POD only: safe to call from
// the non-ARC hook shim after admission and from the ARC replacement module.
#ifdef __cplusplus
extern "C" {
#endif

bool PlampyCCFunctionalEnabled(void);
int PlampyCCThemeType(void); // raw kThemeType: 0 = Plampy, 1 = Pulsar

#ifdef __cplusplus
}
#endif

#endif

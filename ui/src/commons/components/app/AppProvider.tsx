import { StyledEngineProvider, ThemeProvider, useMediaQuery, type PaletteMode } from '@mui/material';
import type { AppPreferenceConfigs, AppSiteMapConfigs, AppThemeConfigs } from 'commons/components/app/AppConfigs';
import { AppStorageKeys } from 'commons/components/app/AppConstants';
import { AppContext, type AppNotificationService } from 'commons/components/app/AppContexts';
import { AppDefaultsPreferencesConfigs } from 'commons/components/app/AppDefaults';
import type { AppSearchService } from 'commons/components/app/AppSearchService';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import AppBarProvider from 'commons/components/app/providers/AppBarProvider';
import AppLayoutProvider from 'commons/components/app/providers/AppLayoutProvider';
import AppLeftNavProvider from 'commons/components/app/providers/AppLeftNavProvider';
import AppSnackbarProvider from 'commons/components/app/providers/AppSnackbarProvider';
import AppUserProvider from 'commons/components/app/providers/AppUserProvider';
import useLocalStorageItem from 'commons/components/utils/hooks/useLocalStorageItem';
import useThemeBuilder from 'commons/components/utils/hooks/useThemeBuilder';
import i18n from 'i18n';
import { useCallback, useMemo, type ReactNode } from 'react';

const { LS_KEY_DARK_MODE } = AppStorageKeys;

export type AppProviderProps<U extends AppUser> = {
  preferences?: AppPreferenceConfigs;
  theme?: AppThemeConfigs;
  sitemap?: AppSiteMapConfigs;
  user?: AppUserService<U>;
  search?: AppSearchService;
  notification?: AppNotificationService;
  children: ReactNode;
};

export default function AppProvider<U extends AppUser>({
  theme,
  user,
  search,
  sitemap,
  notification,
  preferences,
  children
}: AppProviderProps<U>) {
  // Since we can't useAppConfig yet, we explicitly merge default and preferences config
  //  to help figure the default theme mode.
  const { allowThemeSelection, defaultTheme } = { ...AppDefaultsPreferencesConfigs, ...(preferences || {}) };

  // Store theme state in local storage.
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  const [darkMode, setDarkMode] = useLocalStorageItem(LS_KEY_DARK_MODE, defaultTheme === 'dark' || prefersDarkMode);

  // Enforce default theme if selection isn't alloweed.
  const _darkMode = allowThemeSelection ? darkMode : defaultTheme === 'dark';

  // Create MUI Themes.
  const { lightTheme, darkTheme } = useThemeBuilder(theme);

  // Callback to toggle theme.
  const toggleTheme = useCallback(() => setDarkMode(!darkMode), [darkMode, setDarkMode]);

  // Callback to toggle language.
  const toggleLanguage = useCallback(() => i18n.changeLanguage(i18n.language === 'en' ? 'fr' : 'en'), []);

  // Memoize context value to prevent extraneous renders on components that use it.
  const contextValue = useMemo(() => {
    return {
      theme: (darkMode ? 'dark' : 'light') as PaletteMode,
      configs: { preferences, theme, sitemap },
      toggleTheme,
      toggleLanguage
    };
  }, [darkMode, preferences, theme, sitemap, toggleTheme, toggleLanguage]);

  return (
    <AppContext.Provider value={contextValue}>
      <StyledEngineProvider injectFirst>
        <ThemeProvider theme={_darkMode ? darkTheme : lightTheme}>
          <AppUserProvider service={user}>
            <AppBarProvider search={search} notification={notification}>
              <AppLeftNavProvider>
                <AppLayoutProvider>
                  <AppSnackbarProvider>{children}</AppSnackbarProvider>
                </AppLayoutProvider>
              </AppLeftNavProvider>
            </AppBarProvider>
          </AppUserProvider>
        </ThemeProvider>
      </StyledEngineProvider>
    </AppContext.Provider>
  );
}

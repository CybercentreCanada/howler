import { AppContext } from 'commons/components/app/AppContexts';
import {
  AppDefaultsLeftNavConfigs,
  AppDefaultsPreferencesConfigs,
  AppDefaultsSitemapConfigs,
  AppDefaultsThemeConfigs,
  AppDefaultsTopNavConfigs
} from 'commons/components/app/AppDefaults';
import { useContext, useMemo } from 'react';

export function useAppConfigs() {
  const { configs } = useContext(AppContext);
  return useMemo(() => {
    // Merge user provided configs with defaults.
    const { preferences, sitemap, theme } = configs;
    const _configs = {
      preferences: {
        ...AppDefaultsPreferencesConfigs,
        ...(preferences || {}),
        topnav: {
          ...AppDefaultsTopNavConfigs,
          ...(preferences?.topnav || {})
        },
        leftnav: {
          ...AppDefaultsLeftNavConfigs,
          ...(preferences?.leftnav || {})
        }
      },
      sitemap: {
        ...AppDefaultsSitemapConfigs,
        ...(sitemap || {})
      },
      theme: {
        ...AppDefaultsThemeConfigs,
        ...(theme || {})
      }
    };

    // Indicates whether we should render the personalization section of the UserProfile.
    const allowPersonalization =
      _configs.preferences.allowAutoHideTopbar ||
      _configs.preferences.allowBreadcrumbs ||
      _configs.preferences.allowQuickSearch ||
      _configs.preferences.allowReset ||
      _configs.preferences.allowThemeSelection ||
      _configs.preferences.allowLayoutSelection;

    // Rebuild new context.
    return {
      ..._configs,
      allowPersonalization
    };
  }, [configs]);
}

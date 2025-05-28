import { useApp } from 'commons/components/app/hooks/useApp';
import { useAppConfigs } from 'commons/components/app/hooks/useAppConfigs';
import { useMemo } from 'react';

export function useAppLogo() {
  const { theme } = useApp();
  const { preferences } = useAppConfigs();
  return useMemo(() => (theme === 'dark' ? preferences.appIconDark : preferences.appIconLight), [theme, preferences]);
}

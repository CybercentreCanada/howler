import { type PaletteMode } from '@mui/material';
import { useApp } from 'commons/components/app/hooks';
import { useMemo } from 'react';

export type AppThemeType = {
  theme: PaletteMode;
  isDark: boolean;
  isLight: boolean;
  toggle: () => void;
};

export function useAppTheme(): AppThemeType {
  const { theme, toggleTheme } = useApp();
  return useMemo(
    () => ({
      theme,
      isDark: theme === 'dark',
      isLight: theme === 'light',
      toggle: toggleTheme
    }),
    [theme, toggleTheme]
  );
}

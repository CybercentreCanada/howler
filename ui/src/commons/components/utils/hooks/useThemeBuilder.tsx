import { createTheme, type CSSObject, type Components, type PaletteOptions, type Theme } from '@mui/material';
import type { AppThemeConfigs } from 'commons/components/app/AppConfigs';
import { AppDefaultsThemeConfigs } from 'commons/components/app/AppDefaults';
import { useMemo } from 'react';

export const createTuiTheme = (components: Components<Omit<Theme, 'components'>>, palette: PaletteOptions) =>
  createTheme({
    components: {
      ...components,
      MuiCssBaseline: {
        ...(components?.MuiCssBaseline || {}),
        styleOverrides: {
          ...((components.MuiCssBaseline?.styleOverrides as CSSObject) || {}),
          html: {
            width: '100%',
            height: '100%'
          },
          body: {
            width: '100%',
            height: '100%'
          },
          '#root': {
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0
          }
        }
      },
      MuiUseMediaQuery: {
        ...(components.MuiUseMediaQuery || {}),
        defaultProps: {
          noSsr: true
        }
      }
    },
    palette
  });

export default function useThemeBuilder(theme: AppThemeConfigs = AppDefaultsThemeConfigs) {
  return useMemo(
    () => ({
      darkTheme: createTuiTheme(theme.components || {}, {
        mode: 'dark',
        ...(theme?.palette?.dark || {})
      } as PaletteOptions),
      lightTheme: createTuiTheme(theme.components || {}, {
        mode: 'light',
        ...(theme?.palette?.light || {})
      } as PaletteOptions)
    }),
    [theme]
  );
}

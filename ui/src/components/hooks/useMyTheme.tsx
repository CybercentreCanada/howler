import type { AppThemeConfigs } from 'commons/components/app/AppConfigs';

const DEFAULT_THEME: AppThemeConfigs = {
  components: {
    MuiChip: {
      defaultProps: {
        size: 'small'
      }
    }
  },
  palette: {
    dark: {
      background: {
        default: '#181818',
        paper: '#181818'
      },
      primary: {
        main: '#7DA1DB'
      },
      secondary: {
        main: '#C0DEEC'
      }
    },
    light: {
      primary: {
        main: '#0062BF'
      },
      secondary: {
        main: '#619CB7'
      }
    }
  }
};

const useMyTheme = (): AppThemeConfigs => {
  // return LEGACY_THEME;
  // return DARK_BLUE_THEME;
  return DEFAULT_THEME;
};

export default useMyTheme;

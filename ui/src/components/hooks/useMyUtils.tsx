import { useAppTheme } from '@tui/core';
import { darken, lighten } from '@mui/material';
import { useCallback } from 'react';

const useMyUtils = () => {
  const { isDark } = useAppTheme();

  return {
    shiftColor: useCallback(
      (color: string, coefficient: number) => (isDark ? darken : lighten)(color, coefficient),
      [isDark]
    )
  };
};

export default useMyUtils;

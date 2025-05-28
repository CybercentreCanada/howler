import { useMediaQuery, useTheme } from '@mui/material';
import { useMemo } from 'react';

export type PageProps = {
  className?: string;
  width?: string | number;
  height?: string | number;
  margin?: number;
  mb?: number;
  ml?: number;
  mr?: number;
  mt?: number;
};

const PagePropsDefaults = { margin: null, mt: 2, mr: 2, mb: 2, ml: 2 };

export default function usePageProps({
  props,
  defaultOverrides = PagePropsDefaults
}: {
  props: PageProps;
  defaultOverrides?: PageProps;
}) {
  const { className, width, height, margin, mt, mr, mb, ml } = { ...PagePropsDefaults, ...defaultOverrides, ...props };
  const theme = useTheme();
  const divider = useMediaQuery(theme.breakpoints.up('md')) ? 1 : 2;
  return useMemo(
    () => ({
      className,
      style: {
        width,
        height,
        marginBottom: theme.spacing(margin !== null ? margin / divider : mb / divider),
        marginLeft: theme.spacing(margin !== null ? margin / divider : ml / divider),
        marginRight: theme.spacing(margin !== null ? margin / divider : mr / divider),
        marginTop: theme.spacing(margin !== null ? margin / divider : mt / divider)
      }
    }),
    [className, width, height, margin, mt, mr, mb, ml, divider, theme]
  );
}

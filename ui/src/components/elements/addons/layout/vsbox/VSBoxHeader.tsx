import type { BoxProps } from '@mui/material';
import { Box, useTheme } from '@mui/material';
import type { FC, PropsWithChildren } from 'react';
import { useContext, useEffect, useRef } from 'react';
import { useResizeDetector } from 'react-resize-detector';
import { VSBoxContext } from './VSBox';

type VSBoxHeaderProps = Omit<BoxProps, 'children'>;

const VSBoxHeader: FC<PropsWithChildren<VSBoxHeaderProps>> = ({ children, ...boxProps }) => {
  const theme = useTheme();
  const heightRef = useRef<number>();
  const { height, ref } = useResizeDetector({ handleWidth: false });
  const { state, setState } = useContext(VSBoxContext);

  useEffect(() => {
    if (height !== heightRef.current) {
      setState({ ...state, scrollTop: state.top + height });
      heightRef.current = height;
    }
  }, [height, state, setState]);

  return (
    <Box
      {...boxProps}
      ref={ref}
      data-vsbox-header="true"
      position="sticky"
      top={state.top}
      sx={{
        backgroundColor: theme.palette.background.default,
        zIndex: theme.zIndex.appBar - 1,
        ...(boxProps.sx && { ...boxProps.sx })
      }}
    >
      {children}
    </Box>
  );
};

export default VSBoxHeader;

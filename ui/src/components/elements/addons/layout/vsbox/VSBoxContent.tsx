import type { BoxProps } from '@mui/material';
import { Box } from '@mui/material';
import type { FC, PropsWithChildren } from 'react';

const VSBoxContent: FC<PropsWithChildren<Omit<BoxProps, 'children'>>> = ({ children, ...boxProps }) => {
  return (
    <Box data-vsbox-content="true" {...boxProps}>
      {children}
    </Box>
  );
};

export default VSBoxContent;

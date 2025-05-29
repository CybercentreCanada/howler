import { Tabs, useMediaQuery, useTheme } from '@mui/material';
import type { FC, PropsWithChildren } from 'react';

interface TabProps {
  value: string;
}

const HelpTabs: FC<PropsWithChildren<TabProps>> = ({ children, value }) => {
  const theme = useTheme();
  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));

  return (
    <Tabs
      value={value}
      orientation={useHorizontal ? 'horizontal' : 'vertical'}
      variant="scrollable"
      scrollButtons="auto"
      sx={[
        {
          position: 'sticky',
          top: theme.spacing(8),
          flexShrink: 0,
          alignSelf: 'stretch',
          backgroundColor: 'background.paper',
          zIndex: 100,
          '& a': { p: 1, minHeight: 'initial' }
        },
        useHorizontal
          ? {
              marginLeft: '-40px',
              marginRight: '-40px'
            }
          : {
              mr: 3,
              minWidth: '225px',
              '& a': {
                alignItems: 'start'
              }
            }
      ]}
    >
      {children}
    </Tabs>
  );
};

export default HelpTabs;

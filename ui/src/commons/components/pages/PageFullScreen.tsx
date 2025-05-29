import { Fullscreen, FullscreenExit } from '@mui/icons-material';
import { Box, IconButton } from '@mui/material';
import { useAppBar, useAppBarHeight, useAppLayout } from 'commons/components/app/hooks';
import PageContent from 'commons/components/pages/PageContent';
import useFullscreenStatus from 'commons/components/utils/hooks/useFullscreenStatus';
import { memo, useCallback, useRef } from 'react';

type PageFullscreenProps = {
  children: React.ReactNode;
  margin?: number;
  mb?: number;
  ml?: number;
  mr?: number;
  mt?: number;
};

const PageFullscreen = ({ children, margin = null, mb = 2, ml = 2, mr = 2, mt = 2 }: PageFullscreenProps) => {
  const maximizableElement = useRef(null);
  const appBarHeight = useAppBarHeight();
  const layout = useAppLayout();
  const appbar = useAppBar();
  let isFullscreen: boolean;
  let setIsFullscreen: () => void;
  let fullscreenSupported: boolean;

  const barWillHide = layout.current !== 'top' && appbar.autoHide;

  try {
    [isFullscreen, setIsFullscreen] = useFullscreenStatus(maximizableElement);
  } catch (e) {
    fullscreenSupported = false;
    isFullscreen = false;
    setIsFullscreen = undefined;
  }

  const handleEnterFullscreen = useCallback(() => {
    setIsFullscreen();
  }, [setIsFullscreen]);

  const handleExitFullscreen = () => {
    document.exitFullscreen();
  };

  return (
    <Box ref={maximizableElement} component="div" sx={theme => ({ backgroundColor: theme.palette.background.default })}>
      <Box
        component="div"
        sx={theme => ({
          top: barWillHide || isFullscreen ? 0 : appBarHeight,
          float: 'right',
          paddingTop: theme.spacing(2),
          position: 'sticky',
          right: theme.spacing(2),
          zIndex: theme.zIndex.appBar + 1
        })}
      >
        {fullscreenSupported ? null : isFullscreen ? (
          <IconButton onClick={handleExitFullscreen} size="large">
            <FullscreenExit />
          </IconButton>
        ) : (
          <IconButton onClick={handleEnterFullscreen} size="large">
            <Fullscreen />
          </IconButton>
        )}
      </Box>
      <PageContent margin={margin} mb={mb} ml={ml} mr={mr} mt={mt}>
        {children}
      </PageContent>
    </Box>
  );
};

export default memo(PageFullscreen);

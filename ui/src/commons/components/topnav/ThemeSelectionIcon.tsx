import { Tune } from '@mui/icons-material';
import { ClickAwayListener, Fade, IconButton, Paper, Popper, useTheme } from '@mui/material';
import { useAppConfigs } from 'commons/components/app/hooks/useAppConfigs';
import ThemeSelection from 'commons/components/topnav/ThemeSelection';
import { useRef, useState } from 'react';

const ThemeSelectionIcon = () => {
  const anchorEl = useRef();
  const theme = useTheme();
  const { allowPersonalization, preferences } = useAppConfigs();
  const [open, setOpen] = useState<boolean>(false);
  const onThemeSelectionClick = () => setOpen(!open);
  const onClickAway = () => setOpen(false);

  return allowPersonalization || preferences.allowTranslate || preferences.allowReset ? (
    <ClickAwayListener onClickAway={onClickAway}>
      <IconButton ref={anchorEl} color="inherit" aria-label="open drawer" onClick={onThemeSelectionClick} size="large">
        <Tune />
        <Popper
          sx={{ zIndex: theme.zIndex.drawer + 2, minWidth: '280px' }}
          open={open}
          anchorEl={anchorEl.current}
          placement="bottom-end"
          transition
        >
          {({ TransitionProps }) => (
            <Fade {...TransitionProps} timeout={250}>
              <Paper style={{ padding: theme.spacing(1) }} elevation={4}>
                <ThemeSelection />
              </Paper>
            </Fade>
          )}
        </Popper>
      </IconButton>
    </ClickAwayListener>
  ) : null;
};

export default ThemeSelectionIcon;

import { Apps } from '@mui/icons-material';
import {
  Avatar,
  Button,
  ClickAwayListener,
  Fade,
  IconButton,
  Link,
  Paper,
  Popper,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { useAppSwitcher } from 'commons/components/app/hooks/useAppSwitcher';
import { memo, useCallback, useRef, useState } from 'react';

const AppSwitcher = () => {
  const theme = useTheme();
  const anchorRef = useRef();
  const appSwitcher = useAppSwitcher();
  const [open, setOpen] = useState<boolean>(false);
  const isDarkTheme = theme.palette.mode === 'dark';
  const sp1 = theme.spacing(1);
  const isSm = useMediaQuery(theme.breakpoints.down('sm'));

  const onTogglePopper = useCallback(() => setOpen(_open => !_open), []);

  const onClickAway = useCallback(() => setOpen(false), []);

  if (appSwitcher.empty) {
    return null;
  }

  return (
    <ClickAwayListener onClickAway={onClickAway}>
      <IconButton ref={anchorRef} color="inherit" onClick={onTogglePopper} size="large">
        <Apps />
        <Popper
          sx={{ zIndex: theme.zIndex.drawer + 2 }}
          open={open}
          anchorEl={anchorRef.current}
          placement="bottom-end"
          transition
        >
          {({ TransitionProps }) => (
            <Fade {...TransitionProps} timeout={250}>
              <Paper style={{ textAlign: 'center', padding: theme.spacing(1) }} elevation={4}>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'row',
                    flexWrap: 'wrap',
                    maxWidth: appSwitcher.items.length <= 4 || isSm ? '240px' : '360px'
                  }}
                >
                  {appSwitcher.items.map((a, i) => (
                    <div key={`box-${i}`} style={{ width: '120px', padding: sp1, overflow: 'hidden' }}>
                      <Button
                        component={Link}
                        target={a.newWindow ? '_blank' : null}
                        href={a.route}
                        key={`button-${i}`}
                        style={{ display: 'inherit', textDecoration: 'none', fontWeight: 400, color: 'inherit' }}
                      >
                        <div style={{ display: 'inline-flex' }}>
                          <Avatar
                            key={`avatar-${i}`}
                            variant="rounded"
                            alt={a.name}
                            src={
                              isDarkTheme
                                ? typeof a.img_d === 'string'
                                  ? a.img_d
                                  : null
                                : typeof a.img_l === 'string'
                                  ? a.img_l
                                  : null
                            }
                            style={
                              a.img_d === null || typeof a.img_d === 'string'
                                ? { width: theme.spacing(8), height: theme.spacing(8) }
                                : { backgroundColor: 'transparent', width: theme.spacing(8), height: theme.spacing(8) }
                            }
                            sx={{
                              '& img': {
                                objectFit: 'contain'
                              }
                            }}
                          >
                            {isDarkTheme
                              ? a.img_d !== null && typeof a.img_d !== 'string'
                                ? a.img_d
                                : a.alt
                              : a.img_l !== null && typeof a.img_l !== 'string'
                                ? a.img_l
                                : a.alt}
                          </Avatar>
                        </div>
                        <Typography key={`text-${i}`} variant="caption">
                          {a.name}
                        </Typography>
                      </Button>
                    </div>
                  ))}
                </div>
              </Paper>
            </Fade>
          )}
        </Popper>
      </IconButton>
    </ClickAwayListener>
  );
};

export default memo(AppSwitcher);

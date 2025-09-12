import type { StyledComponent } from '@emotion/styled';
import {
  Box,
  ClickAwayListener,
  Divider,
  Fade,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Paper,
  Popper,
  styled,
  Typography,
  useTheme
} from '@mui/material';
import type { AppBarUserMenuElement } from 'commons/components//app/AppConfigs';
import { useAppConfigs, useAppUser } from 'commons/components/app/hooks';
import AppAvatar, { type AppAvatarProps } from 'commons/components/display/AppAvatar';
import ThemeSelection from 'commons/components/topnav/ThemeSelection';
import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';

export const AppUserAvatar: StyledComponent<AppAvatarProps> = styled(AppAvatar)(({ theme }) => ({
  width: theme.spacing(5),
  height: theme.spacing(5),
  [theme.breakpoints.down('sm')]: {
    width: theme.spacing(4),
    height: theme.spacing(4)
  }
}));

type AppBarUserMenuType = 'usermenu' | 'adminmenu';

const UserProfile = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const configs = useAppConfigs();
  const { user } = useAppUser();
  const anchorRef = useRef();
  const location = useLocation();

  const [open, setOpen] = useState<boolean>(false);

  const onProfileClick = useCallback(() => setOpen(_open => !_open), []);
  const onClickAway = useCallback(() => setOpen(false), []);

  const renderThemeSelection = useCallback(
    enabled => {
      if (
        enabled &&
        (configs.allowPersonalization || configs.preferences.allowTranslate || configs.preferences.allowReset)
      ) {
        return (
          <div>
            <Divider />
            <ThemeSelection />
          </div>
        );
      }
      return null;
    },
    [configs.allowPersonalization, configs.preferences.allowTranslate, configs.preferences.allowReset]
  );

  const renderMenu = useCallback(
    (type: AppBarUserMenuType, menuItems: AppBarUserMenuElement[], title: string, i18nKey: string) => {
      if (menuItems !== undefined && menuItems !== null && menuItems.length !== 0) {
        return (
          <div>
            <Divider />
            <List dense subheader={<ListSubheader disableSticky>{i18nKey ? t(i18nKey) : title}</ListSubheader>}>
              {menuItems.map((a, i) =>
                a.element ? (
                  <ListItem key={`${type}-${i}`}>{a.element}</ListItem>
                ) : (
                  <ListItemButton component={Link} to={a.route} key={`${type}-${i}`}>
                    {a.icon && <ListItemIcon>{a.icon}</ListItemIcon>}
                    <ListItemText>{a.i18nKey ? t(a.i18nKey) : a.title}</ListItemText>
                  </ListItemButton>
                )
              )}
            </List>
          </div>
        );
      }
      return null;
    },
    [t]
  );

  useEffect(() => {
    // This effect checks to see if the result of pressing a button was a navigation
    // if so, close the settings bar.
    if (open) {
      setOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return (
    <ClickAwayListener onClickAway={onClickAway}>
      <div>
        <IconButton
          ref={anchorRef}
          edge="end"
          sx={{
            padding: 0,
            marginLeft: theme.spacing(1),
            marginRight: theme.spacing(1)
          }}
          onClick={onProfileClick}
          size="large"
        >
          <AppUserAvatar alt={user.name} url={user.avatar} email={user.email}>
            {user.name
              .split(' ', 2)
              .map(n => n[0].toUpperCase())
              .join('')}
          </AppUserAvatar>
        </IconButton>
        <Popper
          sx={{ zIndex: theme.zIndex.appBar + 200, minWidth: '280px' }}
          open={open}
          anchorEl={anchorRef.current}
          placement="bottom-end"
          transition
        >
          {({ TransitionProps }) => (
            <Fade {...TransitionProps} timeout={250}>
              <Paper style={{ padding: theme.spacing(1) }} elevation={4}>
                <List disablePadding>
                  <ListItem disableGutters dense>
                    <Box
                      sx={{
                        display: 'flex',
                        paddingTop: 2,
                        paddingBottom: 2,
                        paddingLeft: 3,
                        paddingRight: 3,
                        alignItems: 'center'
                      }}
                    >
                      <AppAvatar
                        sx={{ width: theme.spacing(8), height: theme.spacing(8) }}
                        alt={user.name}
                        url={user.avatar}
                        email={user.email}
                      >
                        {user.name
                          .split(' ', 2)
                          .map(n => n[0].toUpperCase())
                          .join('')}
                      </AppAvatar>
                      <Box sx={{ paddingLeft: 2 }}>
                        <Typography variant="body1" noWrap>
                          <b>{user.name}</b>
                        </Typography>
                        <Typography variant="caption" noWrap>
                          {user.email}
                        </Typography>
                      </Box>
                    </Box>
                  </ListItem>
                </List>
                {renderMenu(
                  'usermenu',
                  configs.preferences.topnav.userMenu,
                  configs.preferences.topnav.userMenuTitle,
                  configs.preferences.topnav.userMenuI18nKey
                )}
                {user.is_admin &&
                  renderMenu(
                    'adminmenu',
                    configs.preferences.topnav.adminMenu,
                    configs.preferences.topnav.adminMenuTitle,
                    configs.preferences.topnav.adminMenuI18nKey
                  )}
                {renderThemeSelection(configs.preferences.topnav.themeSelectionMode === 'profile')}
              </Paper>
            </Fade>
          )}
        </Popper>
      </div>
    </ClickAwayListener>
  );
};

export default memo(UserProfile);

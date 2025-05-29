import {
  Divider,
  List,
  ListItemButton,
  ListItemSecondaryAction,
  ListItemText,
  ListSubheader,
  Switch,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import useLocalStorage from 'commons/components//utils/hooks/useLocalStorage';
import { APP_STORAGE_PREFIX } from 'commons/components/app/AppConstants';
import {
  useAppBar,
  useAppBreadcrumbs,
  useAppConfigs,
  useAppLanguage,
  useAppLayout,
  useAppQuickSearch,
  useAppTheme
} from 'commons/components/app/hooks';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

const ThemeSelection = () => {
  const theme = useTheme();
  const { t } = useTranslation();
  const configs = useAppConfigs();
  const layout = useAppLayout();
  const breadcrumbs = useAppBreadcrumbs();
  const language = useAppLanguage();
  const appbar = useAppBar();
  const appTheme = useAppTheme();
  const quicksearch = useAppQuickSearch();
  const localStorage = useLocalStorage(APP_STORAGE_PREFIX);
  const isSmDown = useMediaQuery(theme.breakpoints.down('sm'));

  const clearStorage = () => {
    localStorage.clear();
    window.location.reload();
  };

  return (
    <div>
      {configs.preferences.allowTranslate && (
        <List dense subheader={<ListSubheader disableSticky>{t('app.language')}</ListSubheader>}>
          <ListItemButton dense onClick={language.toggle}>
            <ListItemText style={{ margin: 0 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  flexDirection: 'row',
                  width: '100%',
                  textAlign: 'center',
                  cursor: 'pointer'
                }}
              >
                <Typography component="div" variant="body2">
                  English
                </Typography>
                <div style={{ flexGrow: 1 }}>
                  <Switch checked={language.isFR()} name="langSwitch" />
                </div>
                <Typography component="div" variant="body2">
                  Français
                </Typography>
              </div>
            </ListItemText>
          </ListItemButton>
        </List>
      )}
      {configs.preferences.allowTranslate && configs.allowPersonalization && <Divider />}
      {configs.allowPersonalization && (
        <List dense subheader={<ListSubheader disableSticky>{t('personalization')}</ListSubheader>}>
          {configs.preferences.allowThemeSelection && (
            <ListItemButton onClick={appTheme.toggle}>
              <ListItemText>{t('personalization.dark')}</ListItemText>
              <ListItemSecondaryAction>
                <Switch edge="end" onChange={appTheme.toggle} checked={theme.palette.mode === 'dark'} />
              </ListItemSecondaryAction>
            </ListItemButton>
          )}
          {configs.preferences.allowLayoutSelection && (
            <ListItemButton onClick={layout.toggle}>
              <ListItemText>{t('personalization.sticky')}</ListItemText>
              <ListItemSecondaryAction onClick={layout.toggle}>
                <Switch edge="end" checked={layout.current === 'top'} />
              </ListItemSecondaryAction>
            </ListItemButton>
          )}
          {configs.preferences.allowQuickSearch && !isSmDown && (
            <ListItemButton onClick={quicksearch.toggle}>
              <ListItemText>{t('personalization.quicksearch')}</ListItemText>
              <ListItemSecondaryAction>
                <Switch edge="end" checked={quicksearch.show} onClick={quicksearch.toggle} />
              </ListItemSecondaryAction>
            </ListItemButton>
          )}
          {configs.preferences.allowAutoHideTopbar && (
            <ListItemButton disabled={layout.current === 'top'} onClick={appbar.toggleAutoHide}>
              <ListItemText>{t('personalization.autohideappbar')}</ListItemText>
              <ListItemSecondaryAction>
                <Switch
                  edge="end"
                  disabled={layout.current === 'top'}
                  checked={appbar.autoHide && layout.current !== 'top'}
                  onClick={appbar.toggleAutoHide}
                />
              </ListItemSecondaryAction>
            </ListItemButton>
          )}
          {configs.preferences.allowBreadcrumbs && !isSmDown && (
            <>
              <ListItemButton onClick={breadcrumbs.toggle}>
                <ListItemText>{t('personalization.showbreadcrumbs')}</ListItemText>
                <ListItemSecondaryAction>
                  <Switch edge="end" checked={breadcrumbs.show} onClick={breadcrumbs.toggle} />
                </ListItemSecondaryAction>
              </ListItemButton>
            </>
          )}
        </List>
      )}

      {(configs.preferences.allowTranslate || configs.allowPersonalization) && configs.preferences.allowReset && (
        <Divider />
      )}

      {configs.preferences.allowReset && (
        <List dense>
          <ListItemButton dense onClick={clearStorage}>
            <ListItemText>{t('personalization.reset_text')}</ListItemText>
          </ListItemButton>
        </List>
      )}
    </div>
  );
};

export default memo(ThemeSelection);

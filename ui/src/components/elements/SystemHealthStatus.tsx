import { Check, Error, Warning } from '@mui/icons-material';
import Box from '@mui/material/Box/Box';
import Card from '@mui/material/Card/Card';
import CardContent from '@mui/material/CardContent/CardContent';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Popover from '@mui/material/Popover';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useFetchHealth from '../hooks/useFetchHealth';

const SystemHealthStatus = ({ pollingRateMS = 20000 }) => {
  const pluginHealthUri = '/api/healthz/plugins';
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const { healthStatus, loading } = useFetchHealth({ pollingRateMS, pluginHealthUri });
  const { t } = useTranslation();

  const handleRootMouseEnter = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleRootMouseLeave = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  const loadingElement = <Skeleton variant="rounded" width={168} height={31} id="healthy-status-loading" />;
  const isHealthy = useMemo(() => healthStatus.every(c => c.healthy), [healthStatus]);
  const isCritical = useMemo(() =>
    healthStatus
      .filter(componentHealth => componentHealth.importance === 'critical')
      .some(componentHealth => !componentHealth.healthy), [healthStatus]);

  const getIcon = () => {
    if (isHealthy) {
      return <Check sx={{ mr: 1 }} />;
    }
    if (isCritical) {
      return <Error sx={{ mr: 1 }} />;
    }
    return <Warning sx={{ mr: 1 }} />;
  };

  const healthStatusElement = (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        px: 1.2,
        py: 0.45,
        borderRadius: 2,
        bgcolor: isHealthy ? 'success.dark' : isCritical ? 'error.dark' : 'warning.dark',
        color: 'white',
        fontWeight: 700,
        letterSpacing: 0.7,
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        transition: 'background-color 200ms ease, color 200ms ease'
      }}
      aria-owns={open ? 'mouse-over-popover' : undefined}
      aria-haspopup="true"
      onMouseEnter={handleRootMouseEnter}
      onMouseLeave={handleRootMouseLeave}
      id="healthy-status-root"
    >
      {getIcon()}
      <Typography variant="body2" sx={{ fontSize: '0.9rem', cursor: 'default' }}>
        {isHealthy ? t('healthcheck.healthy') : t('healthcheck.unhealthy')}
      </Typography>
    </Box>
  );

  if (healthStatus.length <= 0 && !loading) {
    return <></>;
  }

  return (
    <div>
      <Popover
        id="mouse-over-popover"
        sx={{ pointerEvents: 'none' }}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left'
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left'
        }}
        disableRestoreFocus
      >
        <Card variant="outlined" sx={{ p: 0, m: 0 }}>
          <CardContent sx={{ p: 0, m: 0, height: 'auto' }}>
            <List sx={{ pl: 1, pr: 1, pb: 0, m: 0 }}>
              {healthStatus.map(componentHealth => (
                <ListItem disablePadding key={componentHealth.name}>
                  <ListItemButton>
                    <ListItemIcon>
                      {componentHealth.healthy ? (
                        <Check
                          titleAccess="healthy-plugin-check"
                          id={`healthy-plugin-check-${componentHealth.name}`}
                          color="success"
                        />
                      ) : (
                        <Error
                          titleAccess="unhealthy-plugin-error"
                          id={`unhealthy-plugin-error-${componentHealth.name}`}
                          color="error"
                        />
                      )}
                    </ListItemIcon>
                    <ListItemText primary={t(`healthcheck.plugin.${componentHealth.name}`)} />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </CardContent>
        </Card>
      </Popover>
      {loading && healthStatus.length === 0 ? loadingElement : healthStatusElement}
    </div>)
  ;
};

export default SystemHealthStatus;

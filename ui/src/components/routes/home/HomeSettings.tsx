import { Edit, Settings } from '@mui/icons-material';
import { FormControl, FormLabel, IconButton, ListItemIcon, Menu, MenuItem, Slider, Tooltip } from '@mui/material';
import { useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const REFRESH_RATES = [15, 30, 60, 300];

interface HomeSettingsProps {
  /** Whether the dashboard is currently in edit mode. Disables the "Edit" menu item. */
  isEditing: boolean;
  /** Current auto-refresh interval in seconds. */
  refreshRate: number;
  /** Called when the user selects a new refresh rate. */
  onRefreshRateChange: (rate: number) => void;
  /** Called when the user clicks the "Edit" menu item. */
  onEdit: () => void;
}

const HomeSettings: FC<HomeSettingsProps> = ({ isEditing, refreshRate, onRefreshRateChange, onEdit }) => {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  return (
    <>
      <Tooltip title={t('page.dashboard.settings.edit')}>
        <IconButton onClick={e => setAnchorEl(e.currentTarget)} size="small">
          <Settings color="primary" />
        </IconButton>
      </Tooltip>
      <Menu id="settings-menu" anchorEl={anchorEl} open={!!anchorEl} onClose={() => setAnchorEl(null)}>
        <MenuItem
          disabled={isEditing}
          onClick={() => {
            setAnchorEl(null);
            onEdit();
          }}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          {t('page.dashboard.settings.edit')}
        </MenuItem>
        <MenuItem disableRipple disableTouchRipple sx={{ '&:hover': { bgcolor: 'transparent' }, cursor: 'default' }}>
          <FormControl sx={{ px: 2, py: 1, minWidth: 250, pointerEvents: 'auto' }}>
            <FormLabel id="refresh-rate-label" sx={{ mb: 2 }}>
              {t('page.dashboard.settings.refreshRate')}
            </FormLabel>
            <Slider
              aria-labelledby="refresh-rate-label"
              value={REFRESH_RATES.indexOf(refreshRate)}
              onChange={(_, value) => onRefreshRateChange(REFRESH_RATES[value as number])}
              step={1}
              marks={[
                { value: 0, label: '15s' },
                { value: 1, label: '30s' },
                { value: 2, label: '1m' },
                { value: 3, label: '5m' }
              ]}
              min={0}
              max={3}
              valueLabelDisplay="auto"
              valueLabelFormat={value => {
                const rates = ['15s', '30s', '1m', '5m'];
                return rates[value] || '';
              }}
            />
          </FormControl>
        </MenuItem>
      </Menu>
    </>
  );
};

export default HomeSettings;

import { AccountTree } from '@mui/icons-material';
import { ListItemText, Menu, MenuItem, Typography } from '@mui/material';
import TuiIconButton from 'components/elements/addons/buttons/CustomIconButton';
import type { FC } from 'react';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const BundleButton: FC<{ ids: string[]; disabled?: boolean }> = ({ ids, disabled = false }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const onClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      if (ids.length === 1) {
        navigate(`/bundles/${ids[0]}`);
      } else {
        setAnchorEl(event.currentTarget);
      }
    },
    [ids, navigate]
  );

  const handleClose = useCallback(() => setAnchorEl(null), []);

  return (
    <>
      <TuiIconButton
        size="small"
        tooltip={t(`hit.panel.bundles.open${ids.length > 1 ? '' : '.prompt'}`)}
        onClick={onClick}
        disabled={disabled}
        aria-disabled={disabled}
        aria-haspopup="true"
        aria-controls={anchorEl ? 'bundle-action-menu' : undefined}
        aria-expanded={anchorEl ? 'true' : undefined}
      >
        <AccountTree />
      </TuiIconButton>
      <Menu
        id="bundle-action-menu"
        anchorEl={anchorEl}
        open={!!anchorEl}
        onClose={handleClose}
        MenuListProps={{
          dense: true,
          'aria-labelledby': `bundle-button`
        }}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right'
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right'
        }}
      >
        {ids.map(id => (
          <MenuItem key={id} onClick={() => navigate(`/bundles/${id}`)}>
            <ListItemText
              primary={t('hit.panel.bundles.open.prompt')}
              secondary={
                <Typography variant="caption" color="text.secondary">
                  {id}
                </Typography>
              }
            />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

export default BundleButton;

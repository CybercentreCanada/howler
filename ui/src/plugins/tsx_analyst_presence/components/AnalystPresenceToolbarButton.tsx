import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import { useSharedUserStatusList } from 'plugins/tsx_hooks/user_status/UserStatusListContext';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AnalystPresenceDrawer } from './AnalystPresenceDrawer';

const AnalystPresenceToolbarButtonContent = () => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const { data: users } = useSharedUserStatusList();

  const onlineCount = useMemo(() => users?.filter(analyst => analyst.status !== null).length ?? 0, [users]);

  const handleOpen = useCallback(() => setIsOpen(true), []);
  const handleClose = useCallback(() => setIsOpen(false), []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        handleClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);

    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, handleClose]);

  return (
    <Box sx={{ mr: 1.5 }}>
      <Button
        variant="outlined"
        color="secondary"
        size="small"
        disableElevation
        onClick={handleOpen}
        aria-expanded={isOpen}
        title={t('tsxAnalystPresence.trigger.tooltip')}
      >
        {t('tsxAnalystPresence.common.analysts')}: {onlineCount}
      </Button>

      <AnalystPresenceDrawer isOpen={isOpen} onClose={handleClose} />
    </Box>
  );
};

export default AnalystPresenceToolbarButtonContent;

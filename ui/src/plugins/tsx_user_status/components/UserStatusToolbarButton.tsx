import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Popper from '@mui/material/Popper';
import Typography from '@mui/material/Typography';
import { useAppUser } from 'commons/components/app/hooks';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useSharedUserStatusList } from 'plugins/tsx_hooks/user_status/UserStatusListContext';
import type { ComponentProps } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { isUserAvailability } from '../utils';
import { UserStatusPanel } from './UserStatusPanel';

const extractShiftHours = (schedule: string) => {
  const match = schedule.match(/(\d{1,2})-(\d{1,2})/);

  if (!match) {
    return null;
  }

  const [, start, end] = match;
  return `${start}-${end}`;
};

export const UserStatusToolbarButton = () => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();

  const anchorRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  const { data: users, refetch: refetchUsers } = useSharedUserStatusList();

  const currentUserStatus = useMemo(() => users?.find(u => u.uname === user.username), [users, user.username]);

  const buttonLabel = useMemo(() => {
    const team = `${t('tsxUserStatus.panel.team.label')}: ${currentUserStatus?.team ?? t('tsxUserStatus.panel.none')}`;
    const schedule = `${t('tsxUserStatus.panel.schedule.label')}: ${currentUserStatus?.schedule ? (extractShiftHours(currentUserStatus.schedule) ?? currentUserStatus.schedule) : t('tsxUserStatus.panel.none')}`;
    const status = `${t('tsxUserStatus.panel.status.label')}: ${currentUserStatus?.status ?? t('tsxUserStatus.panel.none')}`;

    return {
      team,
      schedule,
      status
    };
  }, [t, currentUserStatus]);

  const statusColor = useMemo<ComponentProps<typeof Typography>['color']>(() => {
    if (isUserAvailability(currentUserStatus?.status)) {
      switch (currentUserStatus.status) {
        case 'available':
          return 'success';
        case 'away':
          return 'warning';
        case 'busy':
          return 'error';
        default:
          return 'inherit';
      }
    }

    return 'inherit';
  }, [currentUserStatus]);

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
        ref={anchorRef}
        variant="outlined"
        color="secondary"
        size="medium"
        disableElevation
        onClick={handleOpen}
        aria-expanded={isOpen}
        aria-controls="user-status-popper"
        sx={{ minWidth: 200 }}
        disabled={!currentUserStatus}
      >
        <Typography variant="body2" textAlign="left">
          {buttonLabel.team}
        </Typography>

        <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

        <Typography variant="body2" textAlign="left">
          {buttonLabel.schedule}
        </Typography>

        <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

        <Typography variant="body2" textAlign="left" color={statusColor}>
          {buttonLabel.status}
        </Typography>
      </Button>

      {!!currentUserStatus && (
        <Popper
          id="user-status-popper"
          open={isOpen}
          anchorEl={anchorRef.current}
          placement="bottom"
          disablePortal
          sx={{ zIndex: theme => theme.zIndex.modal }}
        >
          <UserStatusPanel
            currentUserStatus={currentUserStatus}
            onMutationComplete={refetchUsers}
            onClose={handleClose}
          />
        </Popper>
      )}
    </Box>
  );
};

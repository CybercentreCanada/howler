import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { UserStatus } from 'api/status';
import { useAppUser } from 'commons/components/app/hooks';
import { useFetchStatuses } from 'plugins/tsx_hooks/user_status/useFetchStatuses';
import { useMutateUserStatus } from 'plugins/tsx_hooks/user_status/useMutateUserStatus';
import { useSharedUserStatusList } from 'plugins/tsx_hooks/user_status/UserStatusListContext';
import { useCallback, useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAnalystPresenceSnackbar } from '../hooks/useAnalystPresenceSnackbar';
import type { AnalystUser } from '../utils';
import { AnalystPresenceStatusConfirmDialog } from './AnalystPresenceStatusConfirmDialog';

type AnalystPresenceTableDetailsStatusProps = {
  user: AnalystUser;
};

export const AnalystPresenceTableDetailsStatus = ({ user }: AnalystPresenceTableDetailsStatusProps) => {
  const { t } = useTranslation();
  const statusLabelId = useId();
  const { user: currentUser } = useAppUser();
  const { setSnackbarMessage } = useAnalystPresenceSnackbar();

  const [selectedStatus, setSelectedStatus] = useState<UserStatus['status'] | null>(user.status);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  const isViewingSelf = user.uname === currentUser?.username;
  const isStatusChangeAllowed = isViewingSelf || user.status !== null;

  useEffect(() => {
    setSelectedStatus(user.status);
  }, [user.status]);

  const { refetch: refetchUserStatusList } = useSharedUserStatusList();
  const { data: statuses, isLoading: isLoadingStatuses } = useFetchStatuses();

  const { mutate: updateUserStatus, isLoading: isUpdatingUserStatus } = useMutateUserStatus({
    onSuccess: res => {
      refetchUserStatusList();

      if (res.uname === currentUser?.username && res.status === null) {
        window.dispatchEvent(new CustomEvent('howler:handover-report-reminder'));
        return;
      }

      setSnackbarMessage({ type: 'success', message: t('tsxAnalystPresence.success.status.update') });
    },
    onError: () => {
      refetchUserStatusList();
      setSnackbarMessage({ type: 'error', message: t('tsxAnalystPresence.error.status.update') });
    }
  });

  const handleClearStatus = useCallback(() => {
    setSelectedStatus(null);
  }, []);

  const handleConfirm = useCallback(() => {
    setShowConfirmDialog(false);
    updateUserStatus({ uname: user.uname, body: { status: selectedStatus } });
  }, [user.uname, selectedStatus, updateUserStatus]);

  const handleCancel = useCallback(() => {
    setShowConfirmDialog(false);
    setSelectedStatus(user.status);
  }, [user.status]);

  const handleUpdateStatus = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      if (isViewingSelf) {
        handleConfirm();
      } else {
        setShowConfirmDialog(true);
      }
    },
    [isViewingSelf, handleConfirm]
  );

  return (
    <Stack>
      <Typography variant="subtitle1" fontWeight="bold" mb={2.5}>
        {t('tsxAnalystPresence.common.status')}
      </Typography>

      <form onSubmit={handleUpdateStatus}>
        {isStatusChangeAllowed ? (
          <>
            <FormControl fullWidth>
              <InputLabel id={statusLabelId} size="small">
                {t('tsxAnalystPresence.common.status')}
              </InputLabel>

              <Select
                labelId={statusLabelId}
                size="small"
                value={selectedStatus && statuses?.includes(selectedStatus) ? selectedStatus : ''}
                label={t('tsxAnalystPresence.common.status')}
                onChange={e => setSelectedStatus((e.target.value as UserStatus['status']) || null)}
                disabled={isLoadingStatuses || isUpdatingUserStatus}
              >
                {statuses?.map(option => (
                  <MenuItem key={option} value={option}>
                    {option}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Stack direction="row" gap={1} marginTop={3} justifyContent="space-between">
              <Button
                size="small"
                onClick={handleClearStatus}
                color="error"
                disabled={selectedStatus === null || isUpdatingUserStatus}
              >
                {t('tsxAnalystPresence.common.clear')}
              </Button>

              <Button
                type="submit"
                size="small"
                variant="contained"
                disableElevation
                disabled={selectedStatus === user.status || isUpdatingUserStatus}
              >
                {t('tsxAnalystPresence.common.confirm')}
              </Button>
            </Stack>
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">
            {t('tsxAnalystPresence.status.notEditable')}
          </Typography>
        )}
      </form>

      <AnalystPresenceStatusConfirmDialog
        open={showConfirmDialog}
        status={selectedStatus}
        username={user.name}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </Stack>
  );
};

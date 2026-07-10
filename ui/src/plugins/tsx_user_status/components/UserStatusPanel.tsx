import { Info as InfoIcon } from '@mui/icons-material';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { PatchUserStatusBody, UserStatus } from 'api/status';
import { useFetchSchedules } from 'plugins/tsx_hooks/user_status/useFetchSchedules';
import { useFetchStatuses } from 'plugins/tsx_hooks/user_status/useFetchStatuses';
import { useMutateUserStatus } from 'plugins/tsx_hooks/user_status/useMutateUserStatus';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { UpdateErrorMessage } from './UpdateErrorMessage';

type UserStatusPanelProps = {
  currentUserStatus: UserStatus;
  onMutationComplete: () => void;
  onClose: () => void;
};

export const UserStatusPanel = ({ currentUserStatus, onMutationComplete, onClose }: UserStatusPanelProps) => {
  const { t } = useTranslation();

  const [selectedTeam, setSelectedTeam] = useState<string | null>(currentUserStatus.team);
  const [selectedSchedule, setSelectedSchedule] = useState<string | null>(currentUserStatus.schedule);
  const [selectedStatus, setSelectedStatus] = useState<UserStatus['status'] | null>(currentUserStatus.status);

  const { data: statuses, isLoading: isLoadingStatuses } = useFetchStatuses();
  const { data: schedules, isLoading: isLoadingSchedules } = useFetchSchedules();

  const {
    mutate: updateUserStatus,
    isLoading: isUpdatingUserStatus,
    error: updateUserStatusError
  } = useMutateUserStatus({
    onSuccess: res => {
      const hasClearedOwnStatus =
        res.uname === currentUserStatus.uname && res.status !== currentUserStatus.status && res.status === null;

      if (hasClearedOwnStatus) {
        window.dispatchEvent(new CustomEvent('howler:handover-report-reminder'));
      }

      onMutationComplete();
      onClose();
    },
    onError: () => onMutationComplete()
  });

  const teams = useMemo<string[]>(() => {
    if (!schedules) return [];
    return Object.keys(schedules);
  }, [schedules]);

  const teamSpecificSchedules = useMemo<string[]>(() => {
    if (!schedules || !selectedTeam) return [];
    return schedules[selectedTeam] || [];
  }, [schedules, selectedTeam]);

  const isClearEnabled = useMemo(() => {
    return selectedTeam !== null || selectedSchedule !== null || selectedStatus !== null;
  }, [selectedSchedule, selectedStatus, selectedTeam]);

  const isConfirmEnabled = useMemo(() => {
    if (
      selectedTeam === currentUserStatus.team &&
      selectedSchedule === currentUserStatus.schedule &&
      selectedStatus === currentUserStatus.status
    ) {
      return false;
    }

    return true;
  }, [currentUserStatus, selectedSchedule, selectedStatus, selectedTeam]);

  const handleSelectTeam = useCallback((value: string | null) => {
    setSelectedTeam(value);
    setSelectedSchedule(null); // reset schedule when team changes
  }, []);

  const handleSelectSchedule = useCallback((value: string | null) => {
    setSelectedSchedule(value);
  }, []);

  const handleSelectStatus = useCallback((status: UserStatus['status']) => {
    setSelectedStatus(status);
  }, []);

  const handleClear = useCallback(() => {
    setSelectedTeam(null);
    setSelectedSchedule(null);
    setSelectedStatus(null);
  }, []);

  const handleCancel = useCallback(() => {
    setSelectedTeam(currentUserStatus.team);
    setSelectedSchedule(currentUserStatus.schedule);
    setSelectedStatus(currentUserStatus.status);
    onClose();
  }, [currentUserStatus, onClose]);

  const handleConfirm = useCallback(() => {
    if (!isConfirmEnabled) {
      return;
    }

    // PATCH endpoint, update only fields that have changed
    const body: Partial<PatchUserStatusBody> = {};

    if (selectedTeam !== currentUserStatus.team) {
      body.team = selectedTeam;
    }

    if (selectedSchedule !== currentUserStatus.schedule) {
      body.schedule = selectedSchedule;
    }

    if (selectedStatus !== currentUserStatus.status) {
      body.status = selectedStatus;
    }

    updateUserStatus({ uname: currentUserStatus.uname, body });
  }, [
    updateUserStatus,
    currentUserStatus.uname,
    selectedTeam,
    currentUserStatus.team,
    selectedSchedule,
    currentUserStatus.schedule,
    selectedStatus,
    currentUserStatus.status,
    isConfirmEnabled
  ]);

  useEffect(() => {
    setSelectedTeam(currentUserStatus.team);
    setSelectedSchedule(currentUserStatus.schedule);
    setSelectedStatus(currentUserStatus.status);
  }, [currentUserStatus]);

  return (
    <ClickAwayListener onClickAway={onClose}>
      <Paper id="analyst-presence-panel" elevation={4} sx={{ width: 400, mt: 1, pt: 2, pb: 3, px: 3 }}>
        <Typography variant="h6">{t('tsxUserStatus.panel.title')}</Typography>

        <Typography variant="body2" color="text.secondary" mt={0.5}>
          {t('tsxUserStatus.panel.description')}
        </Typography>

        <Stack mt={3} gap={3}>
          <Autocomplete
            fullWidth
            options={teams}
            getOptionLabel={option => option.toString()}
            value={selectedTeam}
            onChange={(_, value) => handleSelectTeam(value)}
            renderInput={params => (
              <TextField {...params} label={t('tsxUserStatus.panel.team.label')} variant="outlined" size="small" />
            )}
            disabled={isLoadingSchedules || isUpdatingUserStatus}
          />

          <Stack>
            <Autocomplete
              fullWidth
              options={teamSpecificSchedules}
              getOptionLabel={option => option.toString()}
              value={selectedSchedule}
              onChange={(_, value) => handleSelectSchedule(value)}
              renderInput={params => (
                <TextField
                  {...params}
                  label={t('tsxUserStatus.panel.schedule.label')}
                  variant="outlined"
                  size="small"
                />
              )}
              disabled={
                isLoadingSchedules || isUpdatingUserStatus || !selectedTeam || teamSpecificSchedules.length === 0
              }
            />

            {!isLoadingSchedules && !selectedTeam && (
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5, ml: 0.5, gap: 0.5 }}>
                <InfoIcon fontSize="small" sx={{ width: 14, height: 14 }} />

                <Typography variant="caption" color="text.secondary">
                  {t('tsxUserStatus.panel.schedule.helperText')}
                </Typography>
              </Box>
            )}
          </Stack>

          <Autocomplete
            fullWidth
            options={statuses || []}
            getOptionLabel={option => option.toString()}
            value={selectedStatus}
            onChange={(_, value) => handleSelectStatus(value)}
            renderInput={params => (
              <TextField
                {...params}
                label={t('tsxUserStatus.panel.status.label')}
                variant="outlined"
                size="small"
                inputProps={{
                  ...params.inputProps,
                  style: {
                    ...(params.inputProps.style || {}),
                    textTransform: 'capitalize'
                  }
                }}
              />
            )}
            disableClearable={false}
            disabled={isLoadingStatuses || isUpdatingUserStatus}
          />
        </Stack>

        {updateUserStatusError && <UpdateErrorMessage message={t('tsxUserStatus.panel.updateErrorMessage')} />}

        <Box sx={{ display: 'flex', gap: 1, mt: 5 }}>
          <Button variant="text" color="inherit" size="small" onClick={handleClear} disabled={!isClearEnabled}>
            {t('tsxUserStatus.panel.clearButton')}
          </Button>

          <Button variant="text" color="inherit" size="small" onClick={handleCancel} sx={{ ml: 'auto' }}>
            {t('tsxUserStatus.panel.cancelButton')}
          </Button>

          <Button
            variant="contained"
            color="primary"
            size="small"
            onClick={handleConfirm}
            disableElevation
            disabled={!isConfirmEnabled || isUpdatingUserStatus}
          >
            {t('tsxUserStatus.panel.confirmButton')}
          </Button>
        </Box>
      </Paper>
    </ClickAwayListener>
  );
};

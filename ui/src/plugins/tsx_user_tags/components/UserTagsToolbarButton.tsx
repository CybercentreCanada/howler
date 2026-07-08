import { Warning as WarningIcon } from '@mui/icons-material';
import { Alert, Badge, Box, Button, Snackbar } from '@mui/material';
import { useUserTagsContext } from 'plugins/tsx_user_tags/components/UserTagsContext';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { UserTagsDrawer } from './UserTagsDrawer';

export const UserTagsToolbarButton = () => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [showUpdateSuccessSnackbar, setShowUpdateSuccessSnackbar] = useState(false);

  const handleOpen = useCallback(() => setIsOpen(true), []);
  const handleClose = useCallback(() => setIsOpen(false), []);

  const { userTags, isLoadingUserTags, isUpdatingUserTags, isUpdateSuccess, resetUpdateStatus } = useUserTagsContext();

  useEffect(() => {
    if (isUpdateSuccess) {
      setShowUpdateSuccessSnackbar(true);
      handleClose();
      resetUpdateStatus();
    }
  }, [isUpdateSuccess, handleClose, resetUpdateStatus]);

  const totalTagsCount = useMemo(
    () => Object.values(userTags).reduce((total, tagArray) => total + tagArray.length, 0),
    [userTags]
  );

  const isLoadingOrUpdating = isLoadingUserTags || isUpdatingUserTags;
  const showAlert = !isLoadingOrUpdating && totalTagsCount === 0;

  return (
    <Box sx={{ mr: 1.5 }}>
      <Badge
        badgeContent={<WarningIcon fontSize="small" color="warning" />}
        aria-label={t('tsxUserTags.toolbarButton.alertBadge')}
        title={t('tsxUserTags.toolbarButton.alertBadge')}
        invisible={!showAlert}
      >
        <Button
          variant="outlined"
          color="secondary"
          size="small"
          disableElevation
          onClick={handleOpen}
          aria-label={t('tsxUserTags.toolbarButton.tooltip')}
          title={t('tsxUserTags.toolbarButton.tooltip')}
        >
          {t('tsxUserTags.toolbarButton')}: {totalTagsCount}
        </Button>
      </Badge>

      <UserTagsDrawer isOpen={isOpen} onClose={handleClose} showAlertMessage={showAlert} />

      <Snackbar
        open={showUpdateSuccessSnackbar}
        autoHideDuration={6000}
        onClose={(_, reason) => {
          if (reason !== 'clickaway') setShowUpdateSuccessSnackbar(false);
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" variant="filled" onClose={() => setShowUpdateSuccessSnackbar(false)}>
          {t('tsxUserTags.updateSuccessMessage')}
        </Alert>
      </Snackbar>
    </Box>
  );
};

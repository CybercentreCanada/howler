import { Clear as ClearIcon, Close as CloseIcon, Restore as RestoreIcon, Save as SaveIcon } from '@mui/icons-material';
import {
  Alert,
  alpha,
  Box,
  Button,
  CircularProgress,
  Drawer,
  IconButton,
  Stack,
  Typography,
  useTheme
} from '@mui/material';
import type { TagCategory, UserTags } from 'api/tags';
import { useUserTagsContext } from 'plugins/tsx_user_tags/components/UserTagsContext';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { UserTagsConfirmCloseDialog } from './UserTagsConfirmCloseDialog';
import { UserTagsDrawerAlertMessage } from './UserTagsDrawerAlertMessage';
import { UserTagsDrawerEditor } from './UserTagsDrawerEditor';

type UserTagsDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  showAlertMessage: boolean;
};

export const UserTagsDrawer = ({ isOpen, onClose, showAlertMessage }: UserTagsDrawerProps) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const {
    userTags,
    updateUserTags,
    tagsDictionary,
    isLoadingTagsDictionary,
    isUpdatingUserTags,
    updateError,
    resetUpdateStatus
  } = useUserTagsContext();

  const [tagsFormState, setTagsFormState] = useState<UserTags>(userTags);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [showConfirmCloseDialog, setShowConfirmCloseDialog] = useState(false);

  const isResetEnabled = useMemo(() => {
    const isAnyCategoryPopulated = Object.values(tagsFormState).some(tags => tags.length > 0);
    return isAnyCategoryPopulated;
  }, [tagsFormState]);

  const hasUnsavedChanges = useMemo(() => {
    const isPortfolioChanged =
      [...tagsFormState.portfolio].sort().join(',') !== [...userTags.portfolio].sort().join(',');
    const isProductsChanged = [...tagsFormState.products].sort().join(',') !== [...userTags.products].sort().join(',');
    const isDisciplinesChanged =
      [...tagsFormState.primary_disciplines].sort().join(',') !== [...userTags.primary_disciplines].sort().join(',');

    return isPortfolioChanged || isProductsChanged || isDisciplinesChanged;
  }, [tagsFormState, userTags]);

  const handleTagsChange = useCallback((category: TagCategory, tags: string[]) => {
    setTagsFormState(prev => ({ ...prev, [category]: tags }));
  }, []);

  const handleReset = () => {
    setTagsFormState({ portfolio: [], products: [], primary_disciplines: [] });
  };

  const handleSave = useCallback(() => {
    updateUserTags(tagsFormState);
  }, [tagsFormState, updateUserTags]);

  const handleClose = useCallback(() => {
    if (hasUnsavedChanges) {
      setShowConfirmCloseDialog(true);
    } else {
      onClose();
    }
  }, [hasUnsavedChanges, onClose]);

  const handleConfirmClose = () => {
    setShowConfirmCloseDialog(false);
    onClose();
  };

  const handleCancelClose = () => {
    setShowConfirmCloseDialog(false);
  };

  useEffect(() => {
    if (isOpen) {
      setTagsFormState(userTags);
    }
  }, [isOpen, userTags]);

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={handleClose}
      disableEscapeKeyDown={isSearchFocused}
      aria-labelledby="user-tags-drawer-title"
      sx={{ '& .MuiDrawer-paper': { width: 720 } }}
    >
      <Stack sx={{ height: '100%' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            py: 1.5,
            pl: 3,
            pr: 1.5,
            borderBottom: '1px solid',
            borderColor: 'divider'
          }}
        >
          <Typography id="user-tags-drawer-title" variant="h6">
            {t('tsxUserTags.drawer.title')}
          </Typography>
          <IconButton size="small" onClick={handleClose} aria-label={t('tsxUserTags.drawer.close')}>
            <CloseIcon />
          </IconButton>
        </Box>

        {showAlertMessage && <UserTagsDrawerAlertMessage />}

        {isLoadingTagsDictionary ? (
          <CircularProgress sx={{ mt: 4, mx: 'auto' }} aria-label={t('tsxUserTags.drawer.loading')} />
        ) : (
          <UserTagsDrawerEditor
            tagsDictionary={tagsDictionary}
            selectedTags={tagsFormState}
            onChange={handleTagsChange}
            onSearchFocusChange={setIsSearchFocused}
          />
        )}

        <Stack mt="auto" sx={{ pt: 3, pb: 2, px: 2, gap: 3, borderTop: '1px solid', borderColor: 'divider' }}>
          {updateError && (
            <Alert
              severity="error"
              variant="outlined"
              onClose={resetUpdateStatus}
              closeText={t('tsxUserTags.drawer.dismiss')}
              sx={{ backgroundColor: alpha(theme.palette.error.main, 0.075) }}
            >
              {t('tsxUserTags.updateErrorMessage')}
            </Alert>
          )}

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1.5 }}>
            <Button
              title={t('tsxUserTags.drawer.resetButton.tooltip')}
              size="large"
              variant="text"
              color="secondary"
              startIcon={<ClearIcon />}
              onClick={handleReset}
              disabled={!isResetEnabled}
              sx={{ mr: 'auto' }}
            >
              {t('tsxUserTags.drawer.resetButton')}
            </Button>

            <Button
              size="large"
              variant="outlined"
              color="secondary"
              startIcon={<RestoreIcon />}
              onClick={() => setTagsFormState(userTags)}
              title={t('tsxUserTags.drawer.revertButton.tooltip')}
              disabled={!hasUnsavedChanges}
            >
              {t('tsxUserTags.drawer.revertButton')}
            </Button>

            <Button
              size="large"
              variant="contained"
              color="primary"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={!hasUnsavedChanges || isUpdatingUserTags}
            >
              {t('tsxUserTags.drawer.saveButton')}
            </Button>
          </Box>
        </Stack>
      </Stack>

      <UserTagsConfirmCloseDialog
        open={showConfirmCloseDialog}
        onConfirm={handleConfirmClose}
        onCancel={handleCancelClose}
      />
    </Drawer>
  );
};

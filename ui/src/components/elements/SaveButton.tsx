import { Save } from '@mui/icons-material';
import { CircularProgress, Fab, Tooltip, Typography, useMediaQuery } from '@mui/material';
import i18n from 'i18n';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const SaveButton: FC<{ save: () => void; disabled?: boolean; loading?: boolean; error?: string }> = ({
  save,
  disabled = false,
  loading = false,
  error
}) => {
  const { t } = useTranslation();

  const isNarrow = useMediaQuery(`(max-width: ${i18n.language === 'en' ? 1275 : 1375}px)`);

  return (
    <Tooltip title={error}>
      <span>
        <Fab
          variant="extended"
          size="large"
          color="primary"
          disabled={disabled}
          sx={theme => ({
            textTransform: 'none',
            position: 'absolute',
            right: isNarrow ? theme.spacing(2) : `calc(100% + ${theme.spacing(2)})`,
            whiteSpace: 'nowrap',
            pointerEvents: 'initial !important',
            ...(isNarrow ? { bottom: theme.spacing(1) } : { top: 0 })
          })}
          onClick={save}
        >
          {loading ? <CircularProgress size={24} sx={{ mr: 1 }} /> : <Save sx={{ mr: 1 }} />}
          <Typography>{t('save')}</Typography>
        </Fab>
      </span>
    </Tooltip>
  );
};

export default SaveButton;

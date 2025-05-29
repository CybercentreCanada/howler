import { Check, Edit } from '@mui/icons-material';
import { Box, CircularProgress, IconButton, Stack, Typography, useTheme } from '@mui/material';
import api from 'api';
import 'chartjs-adapter-moment';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC } from 'react';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import QueryEditor from '../advanced/QueryEditor';

const RuleView: FC<{ analytic: Analytic; setAnalytic: (a: Analytic) => void }> = ({ analytic, setAnalytic }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();

  const [queryLoading, setQueryLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(null);

  const onEdit = useCallback(async () => {
    try {
      if (editing) {
        setQueryLoading(true);
        const result = await dispatchApi(api.analytic.put(analytic.analytic_id, { rule: editValue }), {
          showError: true,
          throwError: true
        });

        setAnalytic(result);

        showSuccessMessage(t('route.analytics.updated'));
      } else {
        setEditValue(analytic.rule);
      }
    } finally {
      setEditing(!editing);
      setQueryLoading(false);
    }
  }, [analytic, dispatchApi, editValue, editing, setAnalytic, showSuccessMessage, t]);

  return (
    <Stack
      spacing={2}
      sx={{
        height: '100%',
        pt: 1,
        px: 1,
        mt: 1,
        border: `thin solid ${theme.palette.divider}`,
        borderRight: `thin solid ${theme.palette.divider}`
      }}
    >
      <Typography variant="h5" sx={{ mt: 2, mb: 1, display: 'flex', flexDirection: 'row' }}>
        <span>{t('route.analytics.rule.title')}</span>
        <span style={{ marginLeft: theme.spacing(1), textTransform: 'capitalize' }}>({analytic?.rule_type})</span>
        <IconButton sx={{ marginLeft: 'auto' }} disabled={queryLoading} onClick={onEdit}>
          {queryLoading ? (
            <CircularProgress size={20} />
          ) : editing ? (
            <Check fontSize="small" />
          ) : (
            <Edit fontSize="small" />
          )}
        </IconButton>
      </Typography>
      <Box sx={{ flex: 1 }}>
        <QueryEditor
          query={editValue ?? analytic?.rule}
          setQuery={editing && setEditValue}
          language={analytic?.rule_type?.replace('sigma', 'yaml') as 'lucene' | 'eql' | 'yaml'}
        />
      </Box>
    </Stack>
  );
};

export default RuleView;

import { OpenInNew } from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  Divider,
  IconButton,
  LinearProgress,
  Skeleton,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import AnalyticLink from 'components/elements/hit/elements/AnalyticLink';
import EscalationChip from 'components/elements/hit/elements/EscalationChip';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import useCase from '../hooks/useCase';

const ResolveModal: FC<{ case: Case; onConfirm: () => void }> = ({ case: _case, onConfirm }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);
  const { config } = useContext(ApiConfigContext);
  const { updateCase } = useCase({ case: _case });

  const [loading, setLoading] = useState(true);
  const [rationale, setRationale] = useState('');
  const [assessment, setAssessment] = useState(null);
  const [hits, setHits] = useState<Hit[]>([]);

  const hitIds = useMemo(
    () =>
      uniq(
        (_case?.items ?? [])
          .filter(item => item.type === 'hit')
          .map(item => item.value)
          .filter(Boolean)
      ),
    [_case?.items]
  );

  const { assess } = useHitActions(hits);

  useEffect(() => {
    (async () => {
      try {
        const result = await dispatchApi(
          api.search.hit.post({
            query: `howler.id:(${hitIds.join(' OR ')}) AND -howler.status:resolved`,
            metadata: ['analytic']
          })
        );

        setHits(result.items);
      } finally {
        setLoading(false);
      }
    })();
  }, [dispatchApi, hitIds]);

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await assess(assessment, true, rationale);
      await updateCase({ status: 'resolved' });
      onConfirm();
      close();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Stack
      spacing={2}
      p={2}
      alignItems="start"
      sx={{ minWidth: 'min(1000px, 60vw)', maxHeight: '100%', height: '100%' }}
    >
      <Typography variant="h4">{t('modal.cases.resolve')}</Typography>
      <Typography>{t('modal.cases.resolve.description')}</Typography>
      <Stack spacing={1} overflow="auto" width="100%" flex={1}>
        <Stack direction="row" spacing={1}>
          <Box flex={1}>
            <TextField
              size="small"
              fullWidth
              placeholder={t('modal.rationale.label')}
              value={rationale}
              onChange={ev => setRationale(ev.target.value)}
            />
          </Box>
          <Box flex={1}>
            <Autocomplete
              size="small"
              value={assessment}
              onChange={(_ev, _assessment) => setAssessment(_assessment)}
              options={config.lookups['howler.assessment']}
              disablePortal
              renderInput={params => (
                <TextField {...params} placeholder={t('hit.details.actions.assessment')} fullWidth />
              )}
            />
          </Box>
        </Stack>
        <Stack position="relative">
          <Divider />
          <LinearProgress sx={{ opacity: +loading }} />
        </Stack>
        {loading
          ? hitIds.map(id => <Skeleton key={id} variant="rounded" height="40px" width="100%" />)
          : hits.map(hit => (
              <Card key={hit.howler.id} sx={{ p: 1, flexShrink: 0 }}>
                <Stack direction="row" alignItems="center" spacing={1} width="100%">
                  <AnalyticLink hit={hit} compressed alignSelf="center" />
                  <EscalationChip hit={hit} layout={HitLayout.DENSE} />
                  <Chip
                    sx={{ width: 'fit-content', display: 'inline-flex' }}
                    label={hit.howler.status}
                    size="small"
                    color="primary"
                  />
                  <div style={{ flex: 1 }} />
                  <IconButton size="small" component={Link} to={`/hits/${hit.howler.id}`}>
                    <OpenInNew fontSize="small" />
                  </IconButton>
                </Stack>
              </Card>
            ))}
      </Stack>
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error" onClick={close}>
          {t('cancel')}
        </Button>
        <Button
          variant="outlined"
          color="success"
          disabled={loading || !assessment || !rationale}
          onClick={handleConfirm}
        >
          {t('confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default ResolveModal;

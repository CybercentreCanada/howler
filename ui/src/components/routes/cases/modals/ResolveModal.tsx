import { KeyboardArrowDown, OpenInNew } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
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
import { RecordContext } from 'components/app/providers/RecordProvider';
import AnalyticLink from 'components/elements/hit/elements/AnalyticLink';
import EscalationChip from 'components/elements/hit/elements/EscalationChip';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import { isNil, uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import useCase from '../hooks/useCase';

const HitEntry: FC<{ hit: Hit; checked?: boolean; onChange?: () => void }> = ({ hit, checked, onChange }) => {
  if (!hit) {
    return <Skeleton variant="rounded" height="40px" width="100%" />;
  }

  return (
    <Accordion key={hit.howler.id} sx={{ flexShrink: 0, px: 0, py: 0 }}>
      <AccordionSummary
        expandIcon={<KeyboardArrowDown />}
        sx={{
          px: 1,
          py: 0,
          minHeight: '48px !important',
          '& > *': {
            margin: '0 !important'
          }
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1} pr={1} width="100%">
          {!isNil(checked) && (
            <Checkbox
              size="small"
              checked={checked}
              onClick={e => {
                onChange?.();

                e.preventDefault();
                e.stopPropagation();
              }}
            />
          )}
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
      </AccordionSummary>
      <AccordionDetails>
        <HitCard id={hit.howler.id} layout={HitLayout.NORMAL} elevation={0} />
      </AccordionDetails>
    </Accordion>
  );
};

const ResolveModal: FC<{ case: Case; onConfirm: () => void }> = ({ case: _case, onConfirm }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);
  const { config } = useContext(ApiConfigContext);
  const { update: updateCase } = useCase({ case: _case });

  const [loading, setLoading] = useState(true);
  const [rationale, setRationale] = useState('');
  const [assessment, setAssessment] = useState(null);
  const [selectedHitIds, setSelectedHitIds] = useState<Set<string>>(new Set());

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

  const loadRecords = useContextSelector(RecordContext, ctx => ctx.loadRecords);
  const records = useContextSelector(RecordContext, ctx => ctx.records);
  const hits = useMemo(() => hitIds.map(id => records[id] as Hit).filter(Boolean), [hitIds, records]);

  const selectedHits = useMemo(() => hits.filter(hit => selectedHitIds.has(hit.howler.id)), [hits, selectedHitIds]);
  const { assess } = useHitActions(selectedHits);

  const unresolvedHits = useMemo(
    () =>
      hitIds.filter(id => {
        const record = records[id];

        if (!record) {
          // Treat missing records as unresolved until they are loaded
          return true;
        }

        return record.howler.status !== 'resolved';
      }),
    [hitIds, records]
  );

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await assess(assessment, true, rationale);

      setSelectedHitIds(new Set());
    } finally {
      setLoading(false);
    }
  };

  const handleToggleHit = useCallback((hitId: string) => {
    setSelectedHitIds(prev => {
      const next = new Set(prev);
      if (next.has(hitId)) {
        next.delete(hitId);
      } else {
        next.add(hitId);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const result = await dispatchApi(
          api.search.hit.post({
            query: `howler.id:(${hitIds.join(' OR ')})`,
            metadata: ['analytic']
          })
        );

        loadRecords(result.items);
      } finally {
        setLoading(false);
      }
    })();
  }, [dispatchApi, hitIds, loadRecords]);

  useEffect(() => {
    if (loading || unresolvedHits.length > 0) {
      return;
    }

    updateCase({ status: 'resolved' }).then(() => {
      onConfirm();
      close();
    });
  }, [close, loading, onConfirm, unresolvedHits.length, updateCase]);

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
              aria-label={t('modal.rationale.label')}
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
                <TextField
                  {...params}
                  placeholder={t('hit.details.actions.assessment')}
                  aria-label={t('hit.details.actions.assessment')}
                  fullWidth
                />
              )}
            />
          </Box>
        </Stack>
        <Stack position="relative">
          <Divider />
          <LinearProgress sx={{ opacity: +loading }} />
        </Stack>
        {hits
          .filter(hit => unresolvedHits.includes(hit.howler.id))
          .map(hit => (
            <HitEntry
              key={hit.howler.id}
              hit={hit}
              checked={selectedHitIds.has(hit.howler.id)}
              onChange={() => handleToggleHit(hit.howler.id)}
            />
          ))}
        <Accordion variant="outlined">
          <AccordionSummary expandIcon={<KeyboardArrowDown />}>{t('modal.cases.alerts.resolved')}</AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1}>
              {hits
                .filter(hit => !unresolvedHits.includes(hit.howler.id))
                .map(hit => (
                  <HitEntry key={hit.howler.id} hit={hit} />
                ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      </Stack>
      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" color="error" onClick={close}>
          {t('cancel')}
        </Button>
        <Button
          variant="outlined"
          color="success"
          disabled={loading || !assessment || !rationale || selectedHitIds.size === 0}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
          onClick={handleConfirm}
        >
          {t('confirm')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default ResolveModal;

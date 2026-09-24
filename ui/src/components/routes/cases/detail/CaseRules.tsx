import { Add, Delete, History } from '@mui/icons-material';
import {
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import useMyApi from 'components/hooks/useMyApi';
import dayjs, { type Dayjs } from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Rule } from 'models/entities/generated/Rule';
import { useCallback, useContext, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router';
import useCase from '../hooks/useCase';
import CreateRuleDialog from './CreateRuleDialog';

const CaseRules: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showModal } = useContext(ModalContext);
  const routeCase = useOutletContext<Case>();
  const { case: _case, update } = useCase({ case: providedCase ?? routeCase, caseId });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [backfillRule, setBackfillRule] = useState<Rule>();
  const [backfillSince, setBackfillSince] = useState<Dayjs>(dayjs().subtract(30, 'day'));
  const [backfillCount, setBackfillCount] = useState<number>();
  const [backfillLoading, setBackfillLoading] = useState(false);

  const handleBackfillDialogClose = useCallback(() => {
    setBackfillRule(undefined);
    setBackfillCount(undefined);
    setBackfillSince(dayjs().subtract(30, 'day'));
  }, []);

  const handleCountBackfill = useCallback(async () => {
    if (!_case?.case_id || !backfillRule?.rule_id || !backfillSince?.isValid()) {
      return;
    }

    setBackfillLoading(true);
    try {
      const response = await dispatchApi(
        api.v2.case.rules.backfill.count.post(_case.case_id, backfillRule.rule_id, backfillSince.toISOString())
      );
      if (response) {
        setBackfillCount(response.count);
      }
    } finally {
      setBackfillLoading(false);
    }
  }, [_case?.case_id, backfillRule, backfillSince, dispatchApi]);

  const handleSubmitBackfill = useCallback(async () => {
    if (!_case?.case_id || !backfillRule?.rule_id || !backfillSince?.isValid() || backfillCount === null) {
      return;
    }

    setBackfillLoading(true);
    try {
      await dispatchApi(
        api.v2.case.rules.backfill.post(_case.case_id, backfillRule.rule_id, backfillSince.toISOString())
      );
      handleBackfillDialogClose();
    } finally {
      setBackfillLoading(false);
    }
  }, [_case?.case_id, backfillRule, backfillSince, backfillCount, dispatchApi, handleBackfillDialogClose]);

  const handleCreateRule = useCallback(
    async (ruleData: Partial<Rule>) => {
      if (!_case?.case_id) {
        return;
      }

      const updatedCase = await dispatchApi(api.v2.case.rules.post(_case.case_id, ruleData));
      if (updatedCase) {
        void update(updatedCase, false);
      }
    },
    [_case, dispatchApi, update]
  );

  const handleDeleteRule = useCallback(
    async (ruleId: string) => {
      if (!_case?.case_id) {
        return;
      }

      showModal(
        <ConfirmDeleteModal
          onConfirm={async () => {
            const updatedCase = await dispatchApi(api.v2.case.rules.del(_case.case_id!, ruleId), { throwError: false });
            if (updatedCase) {
              void update(updatedCase, false);
            }
          }}
        />,
        { height: 'auto' }
      );
    },
    [_case, dispatchApi, showModal, update]
  );

  const handleToggleEnabled = useCallback(
    async (ruleId: string, enabled: boolean) => {
      if (!_case?.case_id) {
        return;
      }

      const updatedCase = await dispatchApi(api.v2.case.rules.put(_case.case_id, ruleId, { enabled }));
      if (updatedCase) {
        void update(updatedCase, false);
      }
    },
    [_case, dispatchApi, update]
  );

  if (!_case) {
    return null;
  }

  const rules = _case.rules ?? [];

  return (
    <Stack spacing={2} sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      <Button
        id="create-rule-button"
        variant="outlined"
        startIcon={<Add />}
        onClick={() => setDialogOpen(true)}
        sx={{ alignSelf: 'end' }}
      >
        {t('page.cases.rules.create')}
      </Button>

      <Card>
        {rules.length === 0 ? (
          <Typography m={2} color="textSecondary" textAlign="center">
            {t('page.cases.rules.empty')}
          </Typography>
        ) : (
          <TableContainer>
            <Table id="rules-table" size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('page.cases.rules.destination')}</TableCell>
                  <TableCell>{t('page.cases.rules.query')}</TableCell>
                  <TableCell>{t('hit.search.index')}</TableCell>
                  <TableCell>{t('page.cases.rules.timeframe')}</TableCell>
                  <TableCell>{t('page.cases.rules.author')}</TableCell>
                  <TableCell align="center">{t('enabled')}</TableCell>
                  <TableCell align="right" />
                </TableRow>
              </TableHead>
              <TableBody>
                {rules.map(rule => (
                  <TableRow key={rule.rule_id} id={`rule-row-${rule.rule_id}`}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {rule.destination}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: 'monospace'
                        }}
                      >
                        {rule.query}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        {(rule.indexes ?? ['hit']).map(idx => (
                          <Chip key={idx} size="small" label={idx} variant="outlined" />
                        ))}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      {rule.timeframe != null ? (
                        <Chip
                          size="small"
                          label={
                            rule.expire_after_resolved
                              ? t('page.cases.rules.timeframe.after_resolved', { days: rule.timeframe })
                              : t('page.cases.rules.timeframe.days', { days: rule.timeframe })
                          }
                          color={rule.expire_after_resolved ? 'info' : 'default'}
                        />
                      ) : (
                        <Chip size="small" label={t('page.cases.rules.no_expiry')} color="success" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{rule.author}</Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Switch
                        id={`rule-toggle-${rule.rule_id}`}
                        checked={rule.enabled ?? true}
                        onChange={(_e, checked) => handleToggleEnabled(rule.rule_id!, checked)}
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={t('page.cases.rules.backfill')}>
                        <IconButton
                          id={`rule-backfill-${rule.rule_id}`}
                          size="small"
                          disabled={rule.enabled === false}
                          onClick={() => setBackfillRule(rule)}
                        >
                          <History fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title={t('delete')}>
                        <IconButton
                          id={`rule-delete-${rule.rule_id}`}
                          size="small"
                          onClick={() => handleDeleteRule(rule.rule_id!)}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>

      <CreateRuleDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onSubmit={handleCreateRule} />
      <Dialog
        open={!!backfillRule}
        onClose={handleBackfillDialogClose}
        maxWidth="sm"
        fullWidth
        id="rule-backfill-dialog"
      >
        <DialogTitle>{t('page.cases.rules.backfill')}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Typography>{t('page.cases.rules.backfill.description')}</Typography>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DateTimePicker
                label={t('page.cases.rules.backfill.since')}
                value={backfillSince}
                onChange={value => {
                  if (!value) {
                    return;
                  }

                  setBackfillSince(value);
                  setBackfillCount(undefined);
                }}
                maxDateTime={dayjs()}
                ampm={false}
                slotProps={{ textField: { id: 'rule-backfill-since', size: 'small', fullWidth: true } }}
              />
            </LocalizationProvider>
            {backfillCount !== null && (
              <Typography id="rule-backfill-confirmation">
                {t('page.cases.rules.backfill.confirm', { count: backfillCount })}
              </Typography>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleBackfillDialogClose}>{t('cancel')}</Button>
          {backfillCount === null ? (
            <Button
              id="rule-backfill-count-button"
              variant="contained"
              onClick={handleCountBackfill}
              disabled={backfillLoading || !backfillSince?.isValid()}
            >
              {t('page.cases.rules.backfill.preview')}
            </Button>
          ) : (
            <Button
              id="rule-backfill-submit-button"
              variant="contained"
              onClick={handleSubmitBackfill}
              disabled={backfillLoading || backfillCount === 0}
            >
              {t('page.cases.rules.backfill.submit')}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

export default CaseRules;

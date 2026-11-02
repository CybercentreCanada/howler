import { Add } from '@mui/icons-material';
import {
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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
import { useCallback, useContext, useRef, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router';
import useCase from '../hooks/useCase';
import CreateRuleDialog from './CreateRuleDialog';
import CaseRuleRow from './CaseRuleRow';

const CaseRules: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showModal } = useContext(ModalContext);
  const routeCase = useOutletContext<Case>();
  const { case: _case, update } = useCase({ case: providedCase ?? routeCase, caseId });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [backfillRule, setBackfillRule] = useState<Rule>();
  const [backfillSince, setBackfillSince] = useState<Dayjs>(dayjs().subtract(30, 'day'));
  const [backfillCount, setBackfillCount] = useState<number | null>(null);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const backfillCountRequestId = useRef(0);

  const invalidateBackfillCountRequest = useCallback(() => {
    backfillCountRequestId.current += 1;
    setBackfillLoading(false);
  }, []);

  const handleBackfillDialogClose = useCallback(() => {
    invalidateBackfillCountRequest();
    setBackfillRule(undefined);
    setBackfillCount(null);
    setBackfillSince(dayjs().subtract(30, 'day'));
  }, [invalidateBackfillCountRequest]);

  const handleCountBackfill = useCallback(async () => {
    if (!_case?.case_id || !backfillRule?.rule_id || !backfillSince?.isValid()) {
      return;
    }

    const requestId = ++backfillCountRequestId.current;
    setBackfillLoading(true);
    try {
      const response = await dispatchApi(
        api.v2.case.rules.backfill.count.post(_case.case_id, backfillRule.rule_id, backfillSince.toISOString())
      );
      if (response && requestId === backfillCountRequestId.current) {
        setBackfillCount(response.count);
      }
    } finally {
      if (requestId === backfillCountRequestId.current) {
        setBackfillLoading(false);
      }
    }
  }, [_case?.case_id, backfillRule, backfillSince, dispatchApi]);

  const handleBackfillDialogOpen = useCallback(
    (rule: Rule) => {
      invalidateBackfillCountRequest();
      setBackfillRule(rule);
      setBackfillCount(null);
      setBackfillSince(dayjs().subtract(30, 'day'));
    },
    [invalidateBackfillCountRequest]
  );

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
                  <CaseRuleRow
                    key={rule.rule_id}
                    rule={rule}
                    onToggleEnabled={enabled => handleToggleEnabled(rule.rule_id!, enabled)}
                    onBackfill={() => handleBackfillDialogOpen(rule)}
                    onDelete={() => handleDeleteRule(rule.rule_id!)}
                  />
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

                  invalidateBackfillCountRequest();
                  setBackfillSince(value);
                  setBackfillCount(null);
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

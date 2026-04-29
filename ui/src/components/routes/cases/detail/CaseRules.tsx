import { Add, Delete } from '@mui/icons-material';
import {
  Button,
  Card,
  Chip,
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
import api from 'api';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Rule } from 'models/entities/generated/Rule';
import { useCallback, useContext, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';
import CreateRuleDialog from './CreateRuleDialog';

const CaseRules: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showModal } = useContext(ModalContext);
  const routeCase = useOutletContext<Case>();
  const { case: _case, update } = useCase({ case: providedCase ?? routeCase, caseId });

  const [dialogOpen, setDialogOpen] = useState(false);

  const handleCreateRule = useCallback(
    async (ruleData: Partial<Rule>) => {
      if (!_case) {
        return;
      }

      const updatedCase = await dispatchApi(api.v2.case.rules.post(_case.case_id, ruleData));
      update(updatedCase, false);
    },
    [_case, dispatchApi, update]
  );

  const handleDeleteRule = useCallback(
    async (ruleId: string) => {
      if (!_case) {
        return;
      }

      showModal(
        <ConfirmDeleteModal
          onConfirm={async () => {
            const updatedCase = await dispatchApi(api.v2.case.rules.del(_case.case_id, ruleId), { throwError: false });
            if (updatedCase) {
              update(updatedCase, false);
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
      if (!_case) {
        return;
      }

      const updatedCase = await dispatchApi(api.v2.case.rules.put(_case.case_id, ruleId, { enabled }));
      update(updatedCase, false);
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
                {rules.map(rule => {
                  const _timeframe = rule.timeframe ? dayjs(rule.timeframe) : null;

                  return (
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
                        {_timeframe ? (
                          <Chip
                            size="small"
                            label={_timeframe.format('YYYY-MM-DD HH:mm')}
                            color={_timeframe.isBefore(dayjs()) ? 'error' : 'default'}
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
                          onChange={(_e, checked) => handleToggleEnabled(rule.rule_id, checked)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title={t('delete')}>
                          <IconButton
                            id={`rule-delete-${rule.rule_id}`}
                            size="small"
                            onClick={() => handleDeleteRule(rule.rule_id)}
                          >
                            <Delete fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>

      <CreateRuleDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onSubmit={handleCreateRule} />
    </Stack>
  );
};

export default CaseRules;

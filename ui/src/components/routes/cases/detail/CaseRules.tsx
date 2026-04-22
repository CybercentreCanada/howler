import { Add, Delete, Rule as RuleIcon } from '@mui/icons-material';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import QueryEditor from 'components/routes/advanced/QueryEditor';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import type { Rule } from 'models/entities/generated/Rule';
import { useCallback, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useOutletContext } from 'react-router-dom';
import useCase from '../hooks/useCase';

const DEFAULT_TIMEFRAME_DAYS = 14;

const CaseRules: FC<{ case?: Case; caseId?: string }> = ({ case: providedCase, caseId }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const routeCase = useOutletContext<Case>();
  const { case: _case, update } = useCase({ case: providedCase ?? routeCase, caseId });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [destination, setDestination] = useState('');
  const [timeframe, setTimeframe] = useState(dayjs().add(DEFAULT_TIMEFRAME_DAYS, 'day').format('YYYY-MM-DDTHH:mm'));
  const [noExpiry, setNoExpiry] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleOpenDialog = useCallback(() => {
    setQuery('');
    setDestination('');
    setTimeframe(dayjs().add(DEFAULT_TIMEFRAME_DAYS, 'day').format('YYYY-MM-DDTHH:mm'));
    setNoExpiry(false);
    setDialogOpen(true);
  }, []);

  const handleCloseDialog = useCallback(() => {
    setDialogOpen(false);
  }, []);

  const handleCreateRule = useCallback(async () => {
    if (!_case || !query.trim() || !destination.trim()) {
      return;
    }

    setCreating(true);
    try {
      const ruleData: Partial<Rule> = {
        query: query.trim(),
        destination: destination.trim(),
        timeframe: noExpiry ? undefined : dayjs(timeframe).toISOString()
      };

      const updatedCase = await dispatchApi(api.v2.case.rules.post(_case.case_id, ruleData));
      update(updatedCase);
      setDialogOpen(false);
    } finally {
      setCreating(false);
    }
  }, [_case, query, destination, noExpiry, timeframe, dispatchApi, update]);

  const handleDeleteRule = useCallback(
    async (ruleId: string) => {
      if (!_case) {
        return;
      }

      try {
        const updatedCase = await dispatchApi(api.v2.case.rules.del(_case.case_id, ruleId));
        update(updatedCase);
      } finally {
        setConfirmDeleteId(null);
      }
    },
    [_case, dispatchApi, update]
  );

  const handleToggleEnabled = useCallback(
    async (ruleId: string, enabled: boolean) => {
      if (!_case) {
        return;
      }

      const updatedCase = await dispatchApi(api.v2.case.rules.patch(_case.case_id, ruleId, { enabled }));
      update(updatedCase);
    },
    [_case, dispatchApi, update]
  );

  if (!_case) {
    return null;
  }

  const rules = _case.rules ?? [];

  return (
    <Stack spacing={2} sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Stack direction="row" alignItems="center" spacing={1}>
          <RuleIcon />
          <Typography variant="h6">{t('page.cases.rules')}</Typography>
        </Stack>
        <Button id="create-rule-button" variant="contained" startIcon={<Add />} onClick={handleOpenDialog}>
          {t('page.cases.rules.create')}
        </Button>
      </Stack>

      <Divider />

      {rules.length === 0 ? (
        <Box id="rules-empty-state" sx={{ textAlign: 'center', py: 4 }}>
          <Typography color="textSecondary">{t('page.cases.rules.empty')}</Typography>
        </Box>
      ) : (
        <TableContainer>
          <Table id="rules-table" size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('page.cases.rules.destination')}</TableCell>
                <TableCell>{t('page.cases.rules.query')}</TableCell>
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
                        fontFamily: 'monospace',
                        maxWidth: 300,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {rule.query}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {rule.timeframe ? (
                      <Chip
                        size="small"
                        label={dayjs(rule.timeframe).format('YYYY-MM-DD HH:mm')}
                        color={dayjs(rule.timeframe).isBefore(dayjs()) ? 'error' : 'default'}
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
                    {confirmDeleteId === rule.rule_id ? (
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Typography variant="caption" color="error">
                          {t('page.cases.rules.delete.confirm')}
                        </Typography>
                        <Button
                          id={`rule-confirm-delete-${rule.rule_id}`}
                          size="small"
                          color="error"
                          onClick={() => handleDeleteRule(rule.rule_id)}
                        >
                          {t('confirm')}
                        </Button>
                        <Button size="small" onClick={() => setConfirmDeleteId(null)}>
                          {t('cancel')}
                        </Button>
                      </Stack>
                    ) : (
                      <Tooltip title={t('delete')}>
                        <IconButton
                          id={`rule-delete-${rule.rule_id}`}
                          size="small"
                          onClick={() => setConfirmDeleteId(rule.rule_id)}
                        >
                          <Delete fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth id="create-rule-dialog">
        <DialogTitle>{t('page.cases.rules.create')}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                {t('page.cases.rules.query')}
              </Typography>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <QueryEditor
                  query={query}
                  setQuery={setQuery}
                  language="lucene"
                  height="120px"
                  id="rule-query-editor"
                />
              </Box>
            </Box>

            <TextField
              id="rule-destination-input"
              label={t('page.cases.rules.destination')}
              value={destination}
              onChange={e => setDestination(e.target.value)}
              fullWidth
              placeholder="alerts/{{howler.analytic}}"
              helperText={t('page.cases.rules.destination.help')}
            />

            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                id="rule-timeframe-input"
                label={t('page.cases.rules.timeframe')}
                type="datetime-local"
                value={timeframe}
                onChange={e => setTimeframe(e.target.value)}
                disabled={noExpiry}
                InputLabelProps={{ shrink: true }}
                sx={{ flex: 1 }}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    id="rule-no-expiry-checkbox"
                    checked={noExpiry}
                    onChange={(_e, checked) => setNoExpiry(checked)}
                  />
                }
                label={t('page.cases.rules.no_expiry')}
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t('cancel')}</Button>
          <Button
            id="rule-submit-button"
            variant="contained"
            onClick={handleCreateRule}
            disabled={creating || !query.trim() || !destination.trim()}
          >
            {t('page.cases.rules.create')}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

export default CaseRules;

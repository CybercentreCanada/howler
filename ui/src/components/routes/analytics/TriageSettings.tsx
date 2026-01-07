import { Check, Delete, Remove } from '@mui/icons-material';
import {
  Card,
  Chip,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  LinearProgress,
  Paper,
  Stack,
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
import type { EditOptions } from 'api/analytic';
import 'chartjs-adapter-dayjs-4';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import EditRow from 'components/elements/EditRow';
import useMyApi from 'components/hooks/useMyApi';
import { capitalize, uniq, without } from 'lodash-es';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC } from 'react';
import { useCallback, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';

const TriageSettings: FC<{ analytic: Analytic; setAnalytic: (a: Analytic) => void }> = ({ analytic, setAnalytic }) => {
  const { dispatchApi } = useMyApi();
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const [loading, setLoading] = useState(false);
  const [rationale, setRationale] = useState(null);

  const updateAnalytic = useCallback(
    async (changes: EditOptions) => {
      try {
        setLoading(true);

        const result = await dispatchApi(api.analytic.put(analytic.analytic_id, changes), {
          throwError: true,
          showError: true
        });

        setAnalytic(result);
      } finally {
        setLoading(false);
      }
    },
    [analytic?.analytic_id, dispatchApi, setAnalytic]
  );

  const selectedAssessments =
    analytic?.triage_settings?.valid_assessments ?? config.lookups?.['howler.assessment'] ?? [];
  const rationales = analytic?.triage_settings?.rationales ?? [];

  return (
    <Stack spacing={2} pt={1}>
      <Divider flexItem />
      <TableContainer
        sx={{
          '& table tr:last-child td': {
            borderBottom: 0
          }
        }}
        component={Paper}
      >
        <Table>
          <TableHead>
            <TableRow>
              <TableCell colSpan={3}>
                <Typography variant="h6">{t('route.analytics.triage.title')}</Typography>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <EditRow
              titleKey="route.analytics.triage.rationale"
              descriptionKey="route.analytics.triage.rationale.description"
              value={analytic?.triage_settings?.skip_rationale ?? false}
              type="checkbox"
              onEdit={async value =>
                updateAnalytic({
                  triage_settings: { skip_rationale: JSON.parse(value) }
                })
              }
            />
            <TableRow>
              <TableCell sx={{ width: '100%', borderBottom: 0, paddingBottom: '0 !important', whiteSpace: 'nowrap' }}>
                {t('route.analytics.triage.assessments')}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={3} sx={{ borderBottom: 0, paddingTop: '0 !important' }}>
                <Stack spacing={1}>
                  <Typography variant="caption" color="text.secondary">
                    {t('route.analytics.triage.assessments.description')}
                  </Typography>
                  <Grid
                    container
                    spacing={1}
                    sx={theme => ({ marginLeft: `${theme.spacing(-1)} !important`, marginTop: `0 !important` })}
                  >
                    {config.lookups?.['howler.assessment']?.map(assessment => {
                      const checked = selectedAssessments.includes(assessment) ?? true;

                      return (
                        <Grid item key={assessment}>
                          <Chip
                            variant="outlined"
                            icon={
                              checked ? (
                                <Check fontSize="small" color="success" />
                              ) : (
                                <Remove fontSize="small" color="error" />
                              )
                            }
                            color={checked ? 'success' : 'error'}
                            label={
                              <Tooltip title={t(`hit.details.asessments.${assessment}.description`)}>
                                <span>{assessment.split('-').map(capitalize).join(' ')}</span>
                              </Tooltip>
                            }
                            onClick={() =>
                              updateAnalytic({
                                triage_settings: {
                                  valid_assessments: checked
                                    ? without(selectedAssessments, assessment)
                                    : uniq([...selectedAssessments, assessment])
                                }
                              })
                            }
                            disabled={loading}
                          />
                        </Grid>
                      );
                    })}
                  </Grid>
                </Stack>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ width: '100%', borderBottom: 0, paddingBottom: '0 !important', whiteSpace: 'nowrap' }}>
                {t('route.analytics.triage.rationales')}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={3} sx={{ borderBottom: 0, paddingTop: '0 !important' }}>
                <Stack spacing={1}>
                  <Typography variant="caption" color="text.secondary">
                    {t('route.analytics.triage.rationales.description')}
                  </Typography>
                  {rationales.map(_rationale => (
                    <Card variant="outlined" key={_rationale}>
                      <Stack direction="row" spacing={1} alignItems="center" px={1}>
                        <Typography flex={1}>{_rationale}</Typography>
                        <IconButton
                          onClick={() =>
                            updateAnalytic({
                              triage_settings: {
                                rationales: without(rationales, _rationale)
                              }
                            })
                          }
                        >
                          <Delete />
                        </IconButton>
                      </Stack>
                    </Card>
                  ))}
                  <Card variant="outlined" sx={{ p: 1 }}>
                    <TextField
                      label={t('route.analytics.rationales.new')}
                      value={rationale}
                      onChange={e => setRationale(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          updateAnalytic({
                            triage_settings: {
                              rationales: uniq([...rationales, rationale])
                            }
                          });
                        }
                      }}
                      fullWidth
                      size="small"
                      InputProps={{
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton
                              size="small"
                              onClick={() =>
                                updateAnalytic({
                                  triage_settings: {
                                    rationales: uniq([...rationales, rationale])
                                  }
                                })
                              }
                            >
                              <Check fontSize="small" />
                            </IconButton>
                          </InputAdornment>
                        )
                      }}
                    />
                  </Card>
                </Stack>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ padding: '0 !important' }}>
                <LinearProgress sx={{ opacity: loading ? 1 : 0 }} />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default TriageSettings;

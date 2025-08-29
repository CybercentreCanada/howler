import {
  Checkbox,
  Divider,
  Grid,
  Paper,
  Stack,
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
import type { EditOptions } from 'api/analytic';
import 'chartjs-adapter-dayjs';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import EditRow from 'components/elements/EditRow';
import useMyApi from 'components/hooks/useMyApi';
import { capitalize, uniq } from 'lodash-es';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC } from 'react';
import { useCallback, useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const TriageSettings: FC<{ analytic: Analytic; setAnalytic: (a: Analytic) => void }> = ({ analytic, setAnalytic }) => {
  const { dispatchApi } = useMyApi();
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const [loading, setLoading] = useState(false);

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

  const selectedAssessments: string[] = useMemo(
    () => analytic?.triage_settings?.valid_assessments ?? config.lookups?.['howler.assessment'] ?? [],
    [analytic?.triage_settings?.valid_assessments, config.lookups]
  );

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
                <Typography variant="caption" color="text.secondary">
                  {t('route.analytics.triage.assessments.description')}
                </Typography>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={3}>
                <Grid container spacing={1}>
                  {config.lookups?.['howler.assessment']?.map(assessment => (
                    <Grid item key={assessment}>
                      <Stack
                        direction="row"
                        alignItems="center"
                        spacing={1}
                        sx={theme => ({
                          border: 'thin solid',
                          borderColor: 'divider',
                          p: 1,
                          borderRadius: theme.shape.borderRadius
                        })}
                      >
                        <Tooltip title={t(`hit.details.asessments.${assessment}.description`)}>
                          <Typography component="span">{assessment.split('-').map(capitalize).join(' ')}</Typography>
                        </Tooltip>
                        <Checkbox
                          checked={selectedAssessments.includes(assessment) ?? true}
                          onChange={(_event, checked) =>
                            updateAnalytic({
                              triage_settings: {
                                valid_assessments: !checked
                                  ? selectedAssessments.filter(_assessment => assessment !== _assessment)
                                  : uniq([...selectedAssessments, assessment])
                              }
                            })
                          }
                          disabled={loading}
                        />
                      </Stack>
                    </Grid>
                  ))}
                </Grid>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
};

export default TriageSettings;

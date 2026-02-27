import { CheckCircleOutline, HourglassBottom, RadioButtonUnchecked, UpdateOutlined } from '@mui/icons-material';
import { Card, Chip, Divider, Grid, Skeleton, Stack, Tooltip, Typography, useTheme } from '@mui/material';
import api from 'api';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import PluginChip from 'components/elements/PluginChip';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import { countBy } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { twitterShort } from 'utils/utils';
import StatusIcon from './components/StatusIcon';

const STATUS_COLORS = {
  resolved: 'success'
};

const CaseCard: FC<{
  case?: Case;
  caseId?: string;
  className?: string;
}> = ({ case: providedCase, caseId, className }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const theme = useTheme();

  const [_case, setCase] = useState(providedCase);

  useEffect(() => {
    if (providedCase) {
      setCase(providedCase);
    }
  }, [providedCase]);

  useEffect(() => {
    if (caseId) {
      dispatchApi(api.v2.case.get(caseId), { throwError: false }).then(setCase);
    }
  }, [caseId, dispatchApi]);

  if (!_case) {
    return <Skeleton variant="rounded" height={250} sx={{ mb: 1 }} className={className} />;
  }

  return (
    <Card
      key={_case.case_id}
      variant="outlined"
      sx={{ p: 1, mb: 1, borderColor: theme.palette[STATUS_COLORS[_case.status]]?.main }}
      className={className}
    >
      <Stack direction="row" alignItems="start" spacing={1}>
        <Stack sx={{ flex: 1 }} spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h6" display="flex" alignItems="start">
              {_case.title}
            </Typography>
            <StatusIcon status={_case.status} />

            <div style={{ flex: 1 }} />

            {_case.start && _case.end && (
              <Tooltip title={dayjs(_case.updated).toString()}>
                <Chip
                  icon={<HourglassBottom fontSize="small" />}
                  size="small"
                  label={twitterShort(_case.start) + ' - ' + twitterShort(_case.end)}
                />
              </Tooltip>
            )}

            <Tooltip title={dayjs(_case.updated).toString()}>
              <Chip icon={<UpdateOutlined fontSize="small" />} size="small" label={twitterShort(_case.updated)} />
            </Tooltip>
          </Stack>
          <Typography variant="caption" color="textSecondary">
            {_case.summary.trim().split('\n')[0]}
          </Typography>
          {_case.participants?.length > 0 && (
            <>
              <Divider flexItem />
              <Stack direction="row" spacing={1}>
                {_case.participants?.map(participant => (
                  <HowlerAvatar key={participant} sx={{ height: '20px', width: '20px' }} userId={participant} />
                ))}
              </Stack>
            </>
          )}
          <Divider flexItem />
          <Grid container spacing={1}>
            {_case.targets?.map(indicator => (
              <Grid key={indicator} item>
                <PluginChip
                  size="small"
                  color="primary"
                  context="casecard"
                  variant="outlined"
                  value={indicator}
                  label={indicator}
                />
              </Grid>
            ))}

            {_case.targets?.length > 0 && (_case.indicators?.length > 0 || _case.threats?.length > 0) && (
              <Grid item>
                <Divider orientation="vertical" />
              </Grid>
            )}

            {_case.indicators?.map(indicator => (
              <Grid item key={indicator}>
                <PluginChip variant="outlined" context="casecard" value={indicator} label={indicator} />
              </Grid>
            ))}

            {_case.indicators?.length > 0 && _case.threats?.length > 0 && (
              <Grid item>
                <Divider orientation="vertical" />
              </Grid>
            )}

            {_case.threats?.map(indicator => (
              <Grid item key={indicator}>
                <PluginChip
                  size="small"
                  color="warning"
                  variant="outlined"
                  context="casecard"
                  value={indicator}
                  label={indicator}
                />
              </Grid>
            ))}
          </Grid>

          {_case.tasks?.length > 0 && (
            <>
              <Divider flexItem />

              <Stack spacing={0.5} alignItems="start">
                {_case.tasks.some(task => task.complete) && (
                  <Chip
                    size="small"
                    color="success"
                    icon={<CheckCircleOutline />}
                    label={`${countBy(_case.tasks, task => task.complete).true} ${t('complete')}`}
                  />
                )}

                {_case.tasks
                  .filter(task => !task.complete)
                  .map(task => (
                    <Chip key={task.id} icon={<RadioButtonUnchecked />} label={task.summary} />
                  ))}
              </Stack>
            </>
          )}
        </Stack>
      </Stack>
    </Card>
  );
};

export default CaseCard;

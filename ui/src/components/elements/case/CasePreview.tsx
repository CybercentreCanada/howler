import { CheckCircleOutline, HourglassBottom, RadioButtonUnchecked, UpdateOutlined } from '@mui/icons-material';
import { Chip, Stack, Tooltip, Typography, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import { countBy } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { twitterShort } from 'utils/utils';
import HowlerAvatar from '../display/HowlerAvatar';
import StatusIcon from './StatusIcon';

type PreviewProps = {
  case: Case;
};

const CasePreview: FC<PreviewProps> = ({ case: _case }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const taskCounts = countBy(_case.tasks, task => task.complete);

  return (
    <Stack
      flex={1}
      spacing={1}
      sx={{ overflow: 'hidden', borderBottom: `thin solid ${theme.palette.divider}`, pb: 1, mb: 0 }}
    >
      <Stack direction="row" spacing={1}>
        <Stack spacing={1}>
          <Typography variant="body1" fontWeight="bold">
            {_case.title}
          </Typography>
          <Typography variant="caption" color="textSecondary">
            {_case.summary.trim().split('\n')[0]}
          </Typography>
        </Stack>
        <StatusIcon status={_case.status} />
        <div style={{ flex: 1 }} />
        <Stack spacing={1} alignItems="end">
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
      </Stack>
      <Stack direction="row" spacing={1}>
        {_case.participants?.length > 0 && (
          <Stack direction="row" spacing={1}>
            {_case.participants?.map(participant => (
              <HowlerAvatar key={participant} sx={{ height: '24px', width: '24px' }} userId={participant} />
            ))}
          </Stack>
        )}
        <Chip color="success" icon={<CheckCircleOutline />} label={`${taskCounts.true} ${t('complete')}`} />
        <Chip icon={<RadioButtonUnchecked />} label={`${taskCounts.false} ${t('incomplete')}`} />
      </Stack>
    </Stack>
  );
};

export default memo(CasePreview);

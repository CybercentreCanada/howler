import { HourglassBottom, UpdateOutlined } from '@mui/icons-material';
import { Chip, Divider, Skeleton, Stack, Tooltip, Typography, useTheme, type CardProps } from '@mui/material';
import api from 'api';
import StatusIcon from 'components/elements/case/StatusIcon';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import useMyApi from 'components/hooks/useMyApi';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { twitterShort } from 'utils/utils';
import HowlerCard from '../display/HowlerCard';

const STATUS_COLORS: Partial<Record<string, 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'>> = {
  resolved: 'success'
};

const CaseCard: FC<{
  case?: Case;
  caseId?: string;
  className?: string;
  slotProps?: { card?: CardProps };
}> = ({ case: providedCase, caseId, className, slotProps }) => {
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
      void dispatchApi(api.v2.case.get(caseId), { throwError: false }).then(result => {
        if (result) {
          setCase(result);
        }
      });
    }
  }, [caseId, dispatchApi]);

  if (!_case) {
    return <Skeleton variant="rounded" height={250} sx={{ mb: 1 }} className={className} />;
  }

  const statusColor = STATUS_COLORS[_case.status!];

  return (
    <HowlerCard
      key={_case.case_id}
      {...slotProps?.card}
      sx={[
        { p: 1, mb: 1, borderColor: statusColor ? theme.palette[statusColor].main : undefined },
        ...(Array.isArray(slotProps?.card?.sx) ? slotProps.card.sx : slotProps?.card?.sx ? [slotProps.card.sx] : [])
      ]}
      className={className}
    >
      <Stack direction="row" alignItems="start" spacing={1}>
        <Stack sx={{ flex: 1 }} spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h6" display="flex" alignItems="start">
              {_case.title}
            </Typography>
            <StatusIcon status={_case.status!} />

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
              <Chip icon={<UpdateOutlined fontSize="small" />} size="small" label={twitterShort(_case.updated!)} />
            </Tooltip>
          </Stack>
          <Typography variant="caption" color="textSecondary">
            {_case.summary?.trim().split('\n')[0]}
          </Typography>
          {(_case.participants?.length ?? 0) > 0 && (
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
              </Stack>
      </Stack>
    </HowlerCard>
  );
};

export default CaseCard;

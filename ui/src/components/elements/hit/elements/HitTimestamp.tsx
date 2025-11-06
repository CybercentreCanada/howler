import { Chip, Tooltip } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import dayjs from 'dayjs';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { formatDate } from 'utils/utils';
import { HitLayout } from '../HitLayout';

const TIMESTAMP_MESSAGES = {
  default: 'retention.safe',
  warning: 'retention.warn',
  error: 'retention.error'
};

const HitTimestamp: FC<{ hit: Hit; layout: HitLayout }> = ({ hit, layout }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const threshold = useMemo(
    () =>
      dayjs().subtract(
        config.configuration.system.retention?.limit_amount ?? 350,
        (config.configuration.system.retention?.limit_unit as dayjs.ManipulateType) ?? 'days'
      ),
    [config.configuration.system.retention?.limit_amount, config.configuration.system.retention?.limit_unit]
  );

  const timestamp = useMemo(() => {
    const validFieldValues = [hit.howler?.expiry, hit.event?.created, hit.timestamp];

    const earliestDate = validFieldValues
      .filter(entry => !!entry)
      .reduce((earliest, current) => {
        return dayjs(earliest).isBefore(current) ? earliest : current;
      });

    return earliestDate;
  }, [hit]);

  const color = useMemo<'default' | 'warning' | 'error'>(() => {
    if (dayjs(timestamp).isBefore(threshold.clone().add(2, 'weeks'))) {
      return 'error';
    }

    if (dayjs(timestamp).isBefore(threshold.clone().add(1, 'months'))) {
      return 'warning';
    }

    return 'default';
  }, [threshold, timestamp]);

  const duration = useMemo(() => {
    if (dayjs(timestamp).isBefore(threshold)) {
      return t('retention.imminent');
    }

    const diff = dayjs(timestamp).diff(threshold, 'seconds');
    const _duration = dayjs.duration(diff, 'seconds');

    return _duration.humanize();
  }, [t, threshold, timestamp]);

  return (
    <Tooltip
      title={t(TIMESTAMP_MESSAGES[color], {
        duration
      })}
    >
      <Chip
        variant="outlined"
        color={color}
        label={formatDate(timestamp)}
        size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
      />
    </Tooltip>
  );
};

export default HitTimestamp;

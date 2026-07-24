import { Icon } from '@iconify/react';
import {
  Card,
  CardContent,
  Skeleton,
  Stack,
  styled,
  Tooltip,
  tooltipClasses,
  Typography,
  useTheme,
  type TooltipProps
} from '@mui/material';
import { get, isEmpty, uniq } from 'lodash-es';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, type FC } from 'react';

const NoMaxWidthTooltip = styled(({ className, ...props }: TooltipProps) => (
  <Tooltip {...props} classes={{ popper: className }} />
))({
  [`& .${tooltipClasses.tooltip}`]: {
    maxWidth: 'none'
  }
});

const CaseAggregate: FC<{
  icon?: string;
  iconColor?: string;
  field?: string;
  records?: Partial<Hit | Event>[];
  title?: string;
  subtitle?: string;
}> = ({ icon, iconColor, field, records, title, subtitle }) => {
  const theme = useTheme();

  if (!title && (!records || !field)) {
    return <Skeleton height={120} />;
  }

  const values = records
    ? uniq(
        records
          .map(_record => get(_record, field!))
          .flat()
          .filter(Boolean)
      )
    : [];

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Stack alignItems="center" spacing={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            {icon && <Icon fontSize="96px" icon={icon} color={iconColor || theme.palette.grey[700]} />}
            <NoMaxWidthTooltip
              title={
                !isEmpty(values) && (
                  <Stack spacing={0.5}>
                    {uniq(values).map(value => (
                      <span key={String(value)}>{String(value)}</span>
                    ))}
                  </Stack>
                )
              }
            >
              <Typography variant="h3">
                {values.length}
                {!isEmpty(values) && !!title && ' - '}
                {title}
              </Typography>
            </NoMaxWidthTooltip>
          </Stack>
          <Typography color="textSecondary">{subtitle}</Typography>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default memo(CaseAggregate);

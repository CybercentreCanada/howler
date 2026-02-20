import { Icon } from '@iconify/react';
import {
  Card,
  CardContent,
  Stack,
  styled,
  Tooltip,
  tooltipClasses,
  Typography,
  useTheme,
  type TooltipProps
} from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { get, isEmpty, uniq } from 'lodash-es';
import { useEffect, useState, type FC } from 'react';

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
  ids?: string[];
  title?: string;
  subtitle?: string;
}> = ({ icon, iconColor, field, ids, title, subtitle }) => {
  const { dispatchApi } = useMyApi();
  const theme = useTheme();

  const [values, setValues] = useState<string[]>([]);

  useEffect(() => {
    if (ids?.length < 1 || !field) {
      return;
    }

    dispatchApi(
      api.v2.search.post(['hit', 'observable'], {
        query: `howler.id:(${ids?.join(' OR ') || '*'})`,
        fl: field
      })
    ).then(response => {
      setValues(uniq(response.items.map(entry => get(entry, field)).flat()));
    });
  }, [dispatchApi, field, ids]);

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
                    {values.map(value => (
                      <span key={value}>{value}</span>
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

export default CaseAggregate;

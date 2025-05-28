import { Chip, Skeleton, Typography, useTheme } from '@mui/material';
import { memo, type FC } from 'react';

export const NotificationSkeleton: FC = memo(() => {
  const theme = useTheme();
  return (
    <div style={{ width: '100%' }}>
      <Typography variant="caption">
        <Skeleton width="30%" />
      </Typography>
      <Typography variant="h6">
        <Skeleton width="50%" />
      </Typography>
      <div style={{ marginTop: theme.spacing(0.25), marginBottom: theme.spacing(1) }}>
        <Typography variant="body2">
          <Skeleton />
        </Typography>
        <Typography variant="body2">
          <Skeleton />
        </Typography>
        <Typography variant="body2">
          <Skeleton />
        </Typography>
      </div>
      <div
        style={{
          width: '100%',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center'
        }}
      >
        <Chip
          size="small"
          variant="outlined"
          label={<Skeleton width="30px" />}
          style={{ margin: theme.spacing(0.25) }}
        />
        <Chip
          size="small"
          variant="outlined"
          label={<Skeleton width="30px" />}
          style={{ margin: theme.spacing(0.25) }}
        />
        <div style={{ flex: 1 }} />

        <Skeleton variant="circular" width={25} height={25} style={{ margin: theme.spacing(0.25) }} />
        <Typography variant="caption" style={{ margin: theme.spacing(0.25) }}>
          <Skeleton width={50} />
        </Typography>

        <Skeleton variant="circular" width={25} height={25} style={{ margin: theme.spacing(0.25) }} />
        <Typography variant="caption" style={{ margin: theme.spacing(0.25) }}>
          <Skeleton width={50} />
        </Typography>
      </div>
    </div>
  );
});

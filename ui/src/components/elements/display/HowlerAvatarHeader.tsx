import { Grid, styled, Typography, useTheme } from '@mui/material';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import HowlerAvatar from './HowlerAvatar';

const AvatarContainer = styled(Grid)(({ theme }) => ({
  marginRight: theme.spacing(4)
}));

const HowlerAvatarHeader: FC<{ user: HowlerUser }> = ({ user }) => {
  const theme = useTheme();
  return (
    <AvatarContainer item sm={12} md={2}>
      <Grid container spacing={2} justifyContent="center">
        <Grid item>
          <HowlerAvatar
            userId={user?.username}
            sx={{
              width: theme.spacing(16),
              height: theme.spacing(16),
              [theme.breakpoints.down('sm')]: {
                width: theme.spacing(24),
                height: theme.spacing(24)
              },
              margin: '0 1rem'
            }}
          />
        </Grid>
        <Grid item xs={12}>
          <Typography textAlign="center">{user?.name ?? ''}</Typography>
        </Grid>
      </Grid>
    </AvatarContainer>
  );
};

export default HowlerAvatarHeader;

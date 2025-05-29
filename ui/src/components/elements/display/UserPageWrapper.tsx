import { Grid, Stack } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC, PropsWithChildren } from 'react';
import HowlerAvatarHeader from './HowlerAvatarHeader';

const UserPageWrapper: FC<PropsWithChildren<{ user: HowlerUser }>> = ({ user, children }) => (
  <PageCenter textAlign="left" mt={6}>
    <Grid container spacing={2} justifyContent="center">
      <HowlerAvatarHeader user={user} />
      <Grid item sm={12} md={9}>
        <Stack direction="column" spacing={2}>
          {children}
        </Stack>
      </Grid>
    </Grid>
  </PageCenter>
);

export default UserPageWrapper;

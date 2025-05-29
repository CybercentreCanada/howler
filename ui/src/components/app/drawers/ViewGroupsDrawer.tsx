import { Box, Divider, Stack, Typography } from '@mui/material';
import type { GroupDetailsResponse } from 'api/user/groups';
import type { FC } from 'react';

type ViewGroupsDrawerProps = {
  groups: GroupDetailsResponse;
};

const ViewGroupsDrawer: FC<ViewGroupsDrawerProps> = ({ groups }) => {
  return (
    <Stack direction="column" spacing={1} sx={{ mt: 2 }} divider={<Divider orientation="horizontal" />}>
      {groups.map(g => (
        <Box key={g.id}>
          <Typography variant="body1">{g.name}</Typography>
          <Typography variant="caption" color="text.disabled">
            {g.id}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
};

export default ViewGroupsDrawer;

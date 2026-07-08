import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import type { AnalystUser } from '../utils';
import { AnalystPresenceTableDetailsStatus } from './AnalystPresenceTableDetailsStatus';
import { AnalystPresenceTableDetailsTags } from './AnalystPresenceTableDetailsTags';

type AnalystDetailsContentProps = {
  user: AnalystUser;
};

export const AnalystPresenceTableDetails = ({ user }: AnalystDetailsContentProps) => {
  return (
    <Stack direction="row" gap={3} py={2} px={3} sx={{ borderTop: '1px solid', borderColor: 'divider' }}>
      <Box flex={1} display="flex" flexDirection="column" sx={{ height: 'auto' }}>
        <AnalystPresenceTableDetailsStatus user={user} />
      </Box>

      <Box flex={1} pl={3} sx={{ borderLeft: '1px solid', borderColor: 'divider', height: 'auto' }}>
        <AnalystPresenceTableDetailsTags tags={user.tags} />
      </Box>
    </Stack>
  );
};

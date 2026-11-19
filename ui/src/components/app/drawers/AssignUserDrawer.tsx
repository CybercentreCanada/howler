import { PersonOff } from '@mui/icons-material';
import { Autocomplete, Avatar, Box, Button, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import useMyUserList from 'components/hooks/useMyUserList';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useCallback, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { groupUserIdentities } from 'utils/userIdentity';

type AssignUserDrawerProps = {
  assignment: string;
  ids: string[];
  onAssigned: (assignment: string) => void;
  skipSubmit?: boolean;
};

const AssignUserDrawer: FC<AssignUserDrawerProps> = ({ assignment, ids, onAssigned, skipSubmit = false }) => {
  const { dispatchApi } = useMyApi();
  const { showInfoMessage } = useMySnackbar();
  const { t } = useTranslation();

  const userIds = useMemo(() => new Set(['*']), []);
  const users = useMyUserList(userIds);
  const { canonicalUsers, getCanonicalUser } = useMemo(() => groupUserIdentities(Object.values(users)), [users]);
  const [assignedUserId, setAssignedUserId] = useState(assignment === 'unassigned' ? null : assignment);
  const [loading, setLoading] = useState(false);

  const canonicalUser =
    assignedUserId && assignedUserId !== 'unassigned' ? getCanonicalUser(assignedUserId) : undefined;
  const usernameToSubmit = canonicalUser?.username ?? assignedUserId;
  const value = useMemo(() => {
    // MUI skips onChange for the same object. Let users explicitly select the canonical option for a duplicate.
    if (canonicalUser && canonicalUser.username !== assignedUserId) {
      return { ...canonicalUser };
    }

    return canonicalUser ?? null;
  }, [assignedUserId, canonicalUser]);

  const onSubmit = useCallback(async () => {
    if (!usernameToSubmit) {
      return;
    }

    if (!skipSubmit) {
      setLoading(true);
      try {
        await Promise.all(
          ids.map(id =>
            dispatchApi(
              api.hit.assign.put(id, {
                value: usernameToSubmit === 'unassigned' ? null : usernameToSubmit
              })
            )
          )
        );

        showInfoMessage(t('app.drawer.hit.assignment.success'));
      } finally {
        setLoading(false);
      }
    }

    onAssigned(usernameToSubmit);
  }, [dispatchApi, ids, onAssigned, showInfoMessage, skipSubmit, t, usernameToSubmit]);

  return (
    <Stack direction="column" spacing={2} sx={{ mt: 2 }}>
      <Typography sx={{ maxWidth: '500px' }}>
        <Trans i18nKey="app.drawer.hit.assignment.description" />
      </Typography>
      <Autocomplete
        disabled={canonicalUsers.length < 1}
        autoComplete
        options={[
          ...canonicalUsers,
          {
            email: t('app.drawer.hit.assignment.unassigned.email'),
            name: t('app.drawer.hit.assignment.unassigned.name'),
            username: 'unassigned'
          } as HowlerUser
        ]}
        filterOptions={(options, { inputValue }) => {
          const query = inputValue.toLowerCase();
          return options.filter(u => u.email?.toLowerCase().includes(query) || u.name.toLowerCase().includes(query));
        }}
        onKeyDown={e => e.stopPropagation()}
        getOptionLabel={(u: HowlerUser) => u.name}
        getOptionKey={u => u.username}
        isOptionEqualToValue={(u, u2) => u.username === u2.username}
        renderOption={({ key, ...props }, u) => {
          return (
            <li key={key} {...props}>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: 'auto 1fr',
                  gridTemplateRows: 'auto auto',
                  gridTemplateAreas: `"profile name"\n"profile email"`,
                  columnGap: 1.5
                }}
              >
                {u.username !== 'unassigned' ? (
                  <HowlerAvatar
                    sx={{ gridArea: 'profile', alignSelf: 'center', height: '32px', width: '32px' }}
                    userId={u.username}
                  />
                ) : (
                  <Avatar sx={{ gridArea: 'profile', alignSelf: 'center', height: '32px', width: '32px' }}>
                    <PersonOff />
                  </Avatar>
                )}
                <Typography sx={{ gridArea: 'name' }} variant="body1">
                  {u.name}
                </Typography>
                <Typography sx={{ gridArea: 'email' }} variant="caption">
                  {u.email}
                </Typography>
              </Box>
            </li>
          );
        }}
        renderInput={params => (
          <TextField {...params} label={<Trans i18nKey="app.drawer.hit.assignment.autocomplete.label" />} />
        )}
        value={value}
        onChange={(_, value: HowlerUser | null) => setAssignedUserId(value?.username ?? null)}
      />
      <Button
        disabled={!usernameToSubmit || assignedUserId === assignment || usernameToSubmit === assignment || loading}
        variant="contained"
        sx={{ alignSelf: 'end' }}
        onClick={onSubmit}
      >
        {loading && <CircularProgress size="24px" sx={{ mr: 1 }} />}
        <Trans i18nKey="button.save" />
      </Button>
    </Stack>
  );
};

export default AssignUserDrawer;

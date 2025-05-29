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
  const [assignedUserId, setAssignedUserId] = useState(assignment === 'unassigned' ? null : assignment);
  const [loading, setLoading] = useState(false);

  const onSubmit = useCallback(async () => {
    if (!skipSubmit) {
      setLoading(true);
      try {
        await Promise.all(
          ids.map(id =>
            dispatchApi(api.hit.assign.put(id, { value: assignedUserId !== 'unassigned' ? assignedUserId : null }))
          )
        );

        showInfoMessage(t('app.drawer.hit.assignment.success'));
      } finally {
        setLoading(false);
      }
    }

    onAssigned(assignedUserId);
  }, [assignedUserId, dispatchApi, ids, onAssigned, showInfoMessage, skipSubmit, t]);

  return (
    <Stack direction="column" spacing={2} sx={{ mt: 2 }}>
      <Typography sx={{ maxWidth: '500px' }}>
        <Trans i18nKey="app.drawer.hit.assignment.description" />
      </Typography>
      <Autocomplete
        disabled={Object.keys(users).length < 1}
        autoComplete
        options={[
          ...Object.values(users),
          {
            email: t('app.drawer.hit.assignment.unassigned.email'),
            name: t('app.drawer.hit.assignment.unassigned.name'),
            username: 'unassigned'
          }
        ]}
        filterOptions={(_users, { inputValue }) =>
          _users.filter(
            u =>
              u.email.toLowerCase().includes(inputValue.toLowerCase()) ||
              u.name.toLowerCase().includes(inputValue.toLowerCase())
          )
        }
        onKeyDown={e => e.stopPropagation()}
        getOptionLabel={(u: HowlerUser) => u.name}
        isOptionEqualToValue={(u, u2) => u.username === u2.username}
        renderOption={(props, u) => {
          return (
            <li key={u.email} {...props}>
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
        value={users[assignedUserId] ?? null}
        onChange={(_, value: HowlerUser) => setAssignedUserId(value?.username)}
      />
      <Button
        disabled={!assignedUserId || assignedUserId === assignment || loading}
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

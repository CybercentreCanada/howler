import type { SxProps, Theme } from '@mui/material';
import { Autocomplete, Box, IconButton, Popover, TextField, Typography } from '@mui/material';
import { UserListContext } from 'components/app/providers/UserListProvider';
import type { FC } from 'react';
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import HowlerAvatar from './display/HowlerAvatar';

const UserList: FC<{
  buttonSx?: SxProps<Theme>;
  userId: string;
  onChange: (userId: string) => void;
  i18nLabel: string;
}> = ({ buttonSx = {}, userId, onChange, i18nLabel }) => {
  const { t } = useTranslation();

  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement>(null);
  const { users, searchUsers } = useContext(UserListContext);

  const userIds = useMemo(() => Object.keys(users), [users]);

  useEffect(() => {
    searchUsers('uname:*');
  }, [searchUsers]);

  return (
    <>
      <IconButton sx={buttonSx} onClick={e => setAnchorEl(e.currentTarget)}>
        <HowlerAvatar userId={userId} />
      </IconButton>
      <Popover
        open={!!anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorEl={anchorEl}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Box sx={{ p: 2 }}>
          <Autocomplete
            sx={{ minWidth: '300px' }}
            options={userIds}
            renderInput={params => <TextField {...params} label={t(i18nLabel)} size="small" />}
            renderOption={(props, _userId) => {
              const user = users[_userId];

              return (
                <li {...props}>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: 'auto 1fr',
                      gridTemplateRows: 'auto auto',
                      gridTemplateAreas: `"profile name"\n"profile email"`,
                      columnGap: 1.5
                    }}
                  >
                    <HowlerAvatar
                      sx={{ gridArea: 'profile', alignSelf: 'center', height: '32px', width: '32px' }}
                      userId={user.username}
                    />
                    <Typography sx={{ gridArea: 'name' }} variant="body1">
                      {user.name}
                    </Typography>
                    <Typography sx={{ gridArea: 'email' }} variant="caption">
                      {user.email}
                    </Typography>
                  </Box>
                </li>
              );
            }}
            value={userId}
            onChange={(__, option) => onChange(option)}
          />
        </Box>
      </Popover>
    </>
  );
};

export default UserList;

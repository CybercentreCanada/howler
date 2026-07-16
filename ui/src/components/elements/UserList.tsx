import type { SxProps, Theme } from '@mui/material';
import { Autocomplete, Box, Chip, IconButton, Popover, TextField, Typography } from '@mui/material';
import { UserListContext } from 'components/app/providers/UserListProvider';
import type { FC } from 'react';
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import HowlerAvatar from './display/HowlerAvatar';

const UserList: FC<{
  buttonSx?: SxProps<Theme>;
  userId?: string;
  onChange?: (userId: string) => void;
  selectedUserIds?: string[];
  onChangeSelectedUserIds?: (userIds: string[]) => void;
  allowMultiple?: boolean;
  i18nLabel: string;
  isModified?: boolean;
}> = ({
  buttonSx = {},
  userId = '',
  onChange = () => {},
  selectedUserIds = [],
  onChangeSelectedUserIds,
  allowMultiple = false,
  i18nLabel,
  isModified = false
}) => {
  const { t } = useTranslation();

  const [anchorEl, setAnchorEl] = useState<HTMLElement>(null);
  const [multiInputValue, setMultiInputValue] = useState('');
  const hasRequestedInitialUsers = useRef(false);
  const { users, searchUsers } = useContext(UserListContext);

  const userOptions = useMemo(() => Object.keys(users), [users]);

  useEffect(() => {
    if (hasRequestedInitialUsers.current) {
      return;
    }

    hasRequestedInitialUsers.current = true;
    searchUsers('uname:*');
  }, [searchUsers]);

  if (isModified) {
    if (allowMultiple) {
      return (
        <Autocomplete
          multiple
          fullWidth
          freeSolo
          options={userOptions}
          value={selectedUserIds}
          inputValue={multiInputValue}
          onInputChange={(__, value) => setMultiInputValue(value)}
          onChange={(__, values) => {
            const normalizedValues = values
              .map(value => (typeof value === 'string' ? value.trim() : ''))
              .filter(Boolean);

            onChangeSelectedUserIds?.(Array.from(new Set(normalizedValues)));
          }}
          renderTags={(value, getTagProps) =>
            value.map((id, index) => {
              const { key, ...tagProps } = getTagProps({ index });
              return (
                <Chip
                  key={key}
                  avatar={<HowlerAvatar userId={id || 'Unknown'} />}
                  label={id}
                  size="small"
                  {...tagProps}
                />
              );
            })
          }
          renderOption={(props, optionUserId) => {
            const { key, ...rest } = props;

            return (
              <li key={key} {...rest}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <HowlerAvatar sx={{ height: '24px', width: '24px' }} userId={optionUserId} />
                  <Typography variant="body2">{optionUserId}</Typography>
                </Box>
              </li>
            );
          }}
          renderInput={params => <TextField {...params} label={t(i18nLabel)} size="small" fullWidth />}
        />
      );
    }

    const avatarUserId = userId || 'Unknown';

    return (
      <Autocomplete
        fullWidth
        freeSolo
        options={userOptions}
        value={userId || null}
        inputValue={userId || ''}
        onInputChange={(__, value) => onChange(value)}
        onChange={(__, option) => onChange(option || '')}
        renderOption={(props, optionUserId) => {
          const { key, ...rest } = props;

          return (
            <li key={key} {...rest}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <HowlerAvatar sx={{ height: '24px', width: '24px' }} userId={optionUserId} />
                <Typography variant="body2">{optionUserId}</Typography>
              </Box>
            </li>
          );
        }}
        renderInput={params => (
          <TextField
            {...params}
            label={t(i18nLabel)}
            size="small"
            fullWidth
            InputProps={{
              ...params.InputProps,
              startAdornment: (
                <>
                  <HowlerAvatar sx={{ height: '24px', width: '24px', marginRight: 1 }} userId={avatarUserId} />
                  {params.InputProps.startAdornment}
                </>
              )
            }}
          />
        )}
      />
    );
  }

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
            options={userOptions}
            renderInput={params => <TextField {...params} label={t(i18nLabel)} size="small" />}
            renderOption={(props, _userId) => {
              const user = users[_userId];
              const { key, ...rest } = props;

              return (
                <li key={key} {...rest}>
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
            value={userId || null}
            onChange={(__, option) => onChange(option || '')}
          />
        </Box>
      </Popover>
    </>
  );
};

export default UserList;

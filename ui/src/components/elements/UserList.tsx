import { Add } from '@mui/icons-material';
import type { SxProps, Theme } from '@mui/material';
import { Autocomplete, AvatarGroup, Box, Chip, IconButton, Popover, Stack, TextField, Typography } from '@mui/material';
import { UserListContext } from 'components/app/providers/UserListProvider';
import type { FC, HTMLAttributes } from 'react';
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import HowlerAvatar from './display/HowlerAvatar';

type UserListOnChange = ((userId: string) => void) | ((userIds: string[]) => void);

const UserList: FC<{
  buttonSx?: SxProps<Theme>;
  userId?: string;
  userIds?: string[];
  onChange?: UserListOnChange;
  selectedUserIds?: string[];
  onChangeSelectedUserIds?: (userIds: string[]) => void;
  allowMultiple?: boolean;
  i18nLabel: string;
  avatarHeight?: number;
  disabled?: boolean;
  multiple?: boolean;
  isModified?: boolean;
}> = ({
  buttonSx = {},
  userId = '',
  userIds: providedUserIds,
  onChange,
  selectedUserIds = [],
  onChangeSelectedUserIds,
  allowMultiple = false,
  i18nLabel,
  avatarHeight = 32,
  disabled = false,
  multiple = false,
  isModified = false
}) => {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [multiInputValue, setMultiInputValue] = useState('');
  const { users, searchUsers, fetchUsers } = useContext(UserListContext);

  const allUserIds = useMemo(() => Object.keys(users), [users]);

  const selectedIds = useMemo(() => {
    if (providedUserIds && providedUserIds.length > 0) {
      return providedUserIds;
    }

    if (userId) {
      return [userId];
    }

    return [] as string[];
  }, [providedUserIds, userId]);

  useEffect(() => {
    searchUsers('uname:*');
  }, [searchUsers]);

  useEffect(() => {
    fetchUsers(new Set(selectedIds.filter(Boolean)));
  }, [fetchUsers, selectedIds]);

  const callSingleOnChange = (value: string) => {
    (onChange as ((nextUserId: string) => void) | undefined)?.(value);
  };

  const callMultiOnChange = (values: string[]) => {
    (onChange as ((nextUserIds: string[]) => void) | undefined)?.(values);
  };

  const renderInput = (params: Parameters<typeof TextField>[0]) => (
    <TextField {...params} label={t(i18nLabel)} size="small" />
  );

  const renderOption = (props: HTMLAttributes<HTMLLIElement>, optionUserId: string) => {
    const { key, ...optionProps } = props as HTMLAttributes<HTMLLIElement> & { key?: string };
    const user = users[optionUserId];

    return (
      <li key={key} {...optionProps}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            gridTemplateRows: 'auto auto',
            gridTemplateAreas: '"profile name" "profile email"',
            columnGap: 1.5
          }}
        >
          <HowlerAvatar
            sx={{ gridArea: 'profile', alignSelf: 'center', height: '32px', width: '32px' }}
            userId={user?.username ?? optionUserId}
          />
          <Typography sx={{ gridArea: 'name' }} variant="body1">
            {user?.name ?? optionUserId}
          </Typography>
          <Typography sx={{ gridArea: 'email' }} variant="caption">
            {user?.email ?? ''}
          </Typography>
        </Box>
      </li>
    );
  };

  if (isModified) {
    if (allowMultiple) {
      return (
        <Autocomplete
          multiple
          fullWidth
          freeSolo
          options={allUserIds}
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
            const { key, ...optionProps } = props;

            return (
              <li key={key} {...optionProps}>
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
        options={allUserIds}
        value={userId || null}
        inputValue={userId || ''}
        onInputChange={(__, value) => callSingleOnChange(value)}
        onChange={(__, option) => callSingleOnChange(option || '')}
        renderOption={(props, optionUserId) => {
          const { key, ...optionProps } = props;

          return (
            <li key={key} {...optionProps}>
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

  const sharedAutocompleteProps = {
    disabled,
    sx: { minWidth: '300px' },
    options: allUserIds,
    renderInput,
    renderOption
  };

  return (
    <>
      {multiple ? (
        <Stack direction="row" spacing={0.25} alignItems="center">
          <AvatarGroup>
            {Array.from(new Set(selectedIds.length > 0 ? selectedIds : ['Unknown'])).map(id => (
              <HowlerAvatar key={id} userId={id} sx={{ height: avatarHeight, width: avatarHeight }} />
            ))}
          </AvatarGroup>
          <IconButton size="small" sx={buttonSx} disabled={disabled} onClick={e => setAnchorEl(e.currentTarget)}>
            <Add />
          </IconButton>
        </Stack>
      ) : (
        <IconButton sx={buttonSx} disabled={disabled} onClick={e => setAnchorEl(e.currentTarget)}>
          <HowlerAvatar userId={selectedIds[0] || 'Unknown'} sx={{ height: avatarHeight, width: avatarHeight }} />
        </IconButton>
      )}
      <Popover
        open={!!anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorEl={anchorEl}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <Box sx={{ p: 2 }}>
          {multiple ? (
            <Autocomplete
              {...sharedAutocompleteProps}
              multiple
              value={selectedIds}
              onChange={(__, options) => callMultiOnChange(options)}
            />
          ) : (
            <Autocomplete
              {...sharedAutocompleteProps}
              value={selectedIds[0] || null}
              onChange={(__, option) => callMultiOnChange(option ? [option] : [])}
            />
          )}
        </Box>
      </Popover>
    </>
  );
};

export default UserList;

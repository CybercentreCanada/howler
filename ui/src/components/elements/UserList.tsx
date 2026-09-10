import { Add } from '@mui/icons-material';
import type { AutocompleteRenderInputParams, SxProps, Theme } from '@mui/material';
import {
  Autocomplete,
  AvatarGroup,
  Box,
  Divider,
  IconButton,
  Popover,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { UserListContext } from 'components/app/providers/UserListProvider';
import { uniq } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC, HTMLAttributes } from 'react';
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Throttler from 'utils/Throttler';
import HowlerAvatar from './display/HowlerAvatar';

const UserEntry: FC<{ user: HowlerUser }> = ({ user }) => {
  return (
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
        userId={user?.username}
      />
      <Typography sx={{ gridArea: 'name' }} variant="body1">
        {user?.name}
      </Typography>
      <Typography sx={{ gridArea: 'email' }} variant="caption">
        {user?.email ?? ''}
      </Typography>
    </Box>
  );
};

const UserList: FC<{
  variant?: 'compact' | 'list';
  buttonSx?: SxProps<Theme>;
  userIds: string[];
  except?: string[];
  onChange: (userIds: string[]) => void;
  i18nLabel: string;
  avatarHeight?: number;
  disabled?: boolean;
  multiple?: boolean;
}> = ({
  buttonSx = {},
  userIds,
  onChange,
  i18nLabel,
  avatarHeight = 32,
  multiple = false,
  disabled = false,
  variant = 'compact',
  except = []
}) => {
  const { t } = useTranslation();

  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const { users, fetchUsers, searchUsers } = useContext(UserListContext);

  const allUserIds = useMemo(() => Object.keys(users), [users]);

  useEffect(() => {
    fetchUsers(new Set(userIds));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userIds]);

  const throttler = useMemo(() => new Throttler(300), []);

  const search = (value: string) => throttler.debounce(() => searchUsers(value));

  const renderInput = (params: AutocompleteRenderInputParams) => (
    <TextField {...params} autoComplete="off" label={t(i18nLabel)} size="small" />
  );

  const renderOption = (props: HTMLAttributes<HTMLLIElement> & { key: any }, optionUserId: string) => {
    const { key, ...optionProps } = props;
    return (
      <li key={key} {...optionProps}>
        <UserEntry user={users[optionUserId]} />
      </li>
    );
  };

  const sharedAutocompleteProps = {
    disabled,
    autocomplete: 'off',
    sx: { minWidth: '300px' },
    options: allUserIds,
    renderInput,
    renderOption,
    onInputChange: (_e: any, value: string) => search(value),
    getOptionDisabled: (optionUserId: string) => userIds.includes(optionUserId) || except.includes(optionUserId)
  };

  const autocomplete = multiple ? (
    <Autocomplete
      {...sharedAutocompleteProps}
      multiple
      value={userIds}
      onChange={(__, options) => {
        onChange(options);
      }}
    />
  ) : (
    <Autocomplete
      {...sharedAutocompleteProps}
      value={userIds?.[0] ?? null}
      onChange={(__, option) => {
        onChange(option ? [option] : []);
      }}
    />
  );

  return (
    <>
      {variant === 'compact' ? (
        multiple ? (
          <Stack direction="row" spacing={0.25} alignItems="center">
            <AvatarGroup>
              {uniq(userIds ?? [null]).map(userId => (
                <HowlerAvatar key={userId} userId={userId} sx={{ height: avatarHeight, width: avatarHeight }} />
              ))}
            </AvatarGroup>
            <IconButton size="small" sx={buttonSx} disabled={disabled} onClick={e => setAnchorEl(e.currentTarget)}>
              <Add />
            </IconButton>
          </Stack>
        ) : (
          <IconButton sx={buttonSx} disabled={disabled} onClick={e => setAnchorEl(e.currentTarget)}>
            <HowlerAvatar userId={userIds[0]} sx={{ height: avatarHeight, width: avatarHeight }} />
          </IconButton>
        )
      ) : multiple ? (
        <Stack width="100%" spacing={1} alignItems="stretch" divider={<Divider flexItem />}>
          {uniq(userIds ?? [null]).map(userId => (
            <UserEntry key={userId} user={users[userId]} />
          ))}
          {autocomplete}
        </Stack>
      ) : (
        <Stack direction="row">
          <HowlerAvatar userId={userIds[0]} sx={{ height: avatarHeight, width: avatarHeight }} />
          <Typography>{userIds[0]}</Typography>
        </Stack>
      )}
      {variant === 'compact' && (
        <Popover
          open={!!anchorEl}
          onClose={() => setAnchorEl(null)}
          anchorEl={anchorEl}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        >
          <Box sx={{ p: 2 }}>{autocomplete}</Box>
        </Popover>
      )}
    </>
  );
};

export default UserList;

import { Person } from '@mui/icons-material';
import { AvatarGroup, Checkbox, Divider, FormControlLabel, Stack, Typography } from '@mui/material';
import { useAppUser } from 'commons/components/app/hooks';
import { UserListContext } from 'components/app/providers/UserListProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import UserList from 'components/elements/UserList';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useContext, useEffect, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const CaseAssigneeFilter: FC<{
  assigneeFilter: string[];
  onChange: (v: string[]) => void;
}> = ({ assigneeFilter, onChange }) => {
  const { t } = useTranslation();
  const { user: currentUser } = useAppUser<HowlerUser>();
  const { users, searchUsers } = useContext(UserListContext);

  useEffect(() => {
    searchUsers('uname:*');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleMyself = useCallback(
    (_: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      if (!currentUser) {
        return;
      }
      onChange(
        checked
          ? [...assigneeFilter.filter(a => a !== currentUser.username), currentUser.username]
          : assigneeFilter.filter(a => a !== currentUser.username)
      );
    },
    [currentUser, assigneeFilter, onChange]
  );

  return (
    <ChipPopper
      icon={
        assigneeFilter.length > 0 ? (
          <AvatarGroup sx={{ '& .MuiAvatar-root': { height: 18, width: 18, fontSize: '0.6rem' } }}>
            {assigneeFilter.map(u => (
              <HowlerAvatar key={u} userId={u} sx={{ height: 18, width: 18 }} />
            ))}
          </AvatarGroup>
        ) : (
          <Person fontSize="small" />
        )
      }
      label={
        <Typography variant="body2">
          {assigneeFilter.length === 0
            ? t('route.cases.filter.assignee')
            : assigneeFilter.length === 1
              ? (users[assigneeFilter[0]]?.name ?? assigneeFilter[0])
              : `${assigneeFilter.length} ${t('route.cases.filter.assignees')}`}
        </Typography>
      }
      minWidth="260px"
      slotProps={{ chip: { size: 'small', color: assigneeFilter.length > 0 ? 'primary' : 'default' } }}
    >
      <Stack direction="row" divider={<Divider orientation="vertical" flexItem />} spacing={1}>
        <UserList userIds={assigneeFilter} onChange={onChange} i18nLabel="route.cases.filter.assignee" multiple />
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={currentUser ? assigneeFilter.includes(currentUser.username) : false}
              onChange={toggleMyself}
            />
          }
          label={t('route.cases.filter.myself')}
        />
      </Stack>
    </ChipPopper>
  );
};

export default CaseAssigneeFilter;

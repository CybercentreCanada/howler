import { Delete, PersonAdd } from '@mui/icons-material';
import {
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  type ButtonProps
} from '@mui/material';
import { useAppUser } from '@tui/core';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import useMyUserList from 'components/hooks/useMyUserList';
import { isEqual } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';
import CustomButton from '../addons/buttons/CustomButton';
import FlexOne from '../addons/layout/FlexOne';
import HowlerAvatar from '../display/HowlerAvatar';
import UserList from '../UserList';
import type { MemberItem, Ownership } from './types';
import { getAllMembers } from './utils';

export interface MembershipManagementProps<T extends Ownership> {
  size?: ButtonProps['size'];
  type: 'action' | 'view' | 'dossier';
  entity?: T;
  onChange: (entity: T) => void;
}

export const MembershipManagement = <T extends Ownership>({
  type,
  entity,
  onChange,
  size
}: MembershipManagementProps<T>) => {
  const params = useParams();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { user } = useAppUser<HowlerUser>();
  const { showSuccessMessage, showWarningMessage, showErrorMessage } = useMySnackbar();

  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [memberQuery, setMemberQuery] = useState('');
  const [privilege, setPrivilege] = useState<MemberItem[1]>('members');
  const [open, setOpen] = useState(false);

  const canManageMembership =
    entity &&
    user &&
    (entity.owner === user.username || entity.admins?.includes(user.username) || !!user.roles?.includes('admin'));

  const members = getAllMembers(entity);
  const users = useMyUserList(members.map(([member]) => member));

  const handleAddMember = useCallback(async () => {
    if (selectedUserIds.length === 0) {
      showWarningMessage(t('membership.message.warning'));
      return;
    }

    try {
      const updatedEntity = (await dispatchApi(
        api[type].permission.put(params.id!, {
          privilege,
          user_ids: selectedUserIds
        })
      )) as T | undefined;

      if (!updatedEntity) {
        throw new Error('Updated Entity was not returned.');
      }

      showSuccessMessage(t('membership.message.success'));

      onChange(updatedEntity);

      setSelectedUserIds([]);
      setMemberQuery('');
    } catch {
      showErrorMessage(t('membership.message.error'));
    }
  }, [
    dispatchApi,
    params.id,
    selectedUserIds,
    privilege,
    t,
    showSuccessMessage,
    showErrorMessage,
    showWarningMessage,
    type,
    onChange
  ]);

  // Keep the targeted privilege explicit so we remove the intended permission entry.
  const handleRemoveMember = useCallback(
    async (user_id: string, targetPrivilege: string) => {
      try {
        const updatedEntity = (await dispatchApi(
          api[type].permission.delete(params.id!, {
            privilege: targetPrivilege,
            user_ids: [user_id]
          }),
          {
            throwError: false
          }
        )) as T | undefined;

        if (!updatedEntity) {
          throw new Error('Updated Entity was not returned.');
        }

        showSuccessMessage(t('membership.message.success'));

        onChange(updatedEntity);
      } catch {
        showErrorMessage(t('membership.message.error'));
      }
    },
    [dispatchApi, params.id, type, onChange, showErrorMessage, t, showSuccessMessage]
  );

  useEffect(() => {
    if (open) {
      // Reset modal state each time it opens to avoid leaking stale UI state.
      setSelectedUserIds([]);
      setMemberQuery('');
      setPrivilege('members');
    }
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const canAssignOwner =
    !!user && (user.roles?.includes('admin') || members.some(member => isEqual(member, [user.username, 'owner'])));

  const availablePrivileges: MemberItem[1][] = canAssignOwner ? ['owner', 'admins', 'members'] : ['admins', 'members'];

  const getPrivilegeLabel = useCallback(
    (privilege: MemberItem[1]) => {
      return t(`membership.privilege.${privilege}`);
    },
    [t]
  );

  const filteredMembers = useMemo(
    () =>
      members.filter(([member, privilege]) => {
        const normalizedQuery = memberQuery.trim().toLowerCase();

        if (!normalizedQuery) {
          return true;
        }

        return (
          member.toLowerCase().includes(normalizedQuery) ||
          privilege.toLowerCase().includes(normalizedQuery) ||
          getPrivilegeLabel(privilege).toLowerCase().includes(normalizedQuery)
        );
      }),
    [members, getPrivilegeLabel, memberQuery]
  );

  if (!canManageMembership) {
    return null;
  }

  return (
    <>
      <CustomButton
        sx={{ flexShrink: 0 }}
        variant="outlined"
        startIcon={<PersonAdd />}
        onClick={() => setOpen(true)}
        size={size}
      >
        {t('membership.manage')}
      </CustomButton>
      <Dialog open={open} onClose={() => setOpen(false)} slotProps={{ paper: { sx: { maxWidth: '50vw' } } }}>
        <DialogTitle>{t('membership.manage')}</DialogTitle>
        <DialogContent sx={{ minHeight: '300px', maxWidth: '80vw', display: 'flex', flexDirection: 'column' }}>
          <Stack
            direction="row"
            divider={<Divider orientation="vertical" flexItem />}
            spacing={1}
            flex={1}
            alignItems="stretch"
            pt={0.5}
          >
            <Stack spacing={1}>
              <TextField
                fullWidth
                size="small"
                label={t('search')}
                value={memberQuery}
                onChange={event => setMemberQuery(event.target.value)}
                sx={{ minWidth: '300px' }}
              />
              <List>
                {filteredMembers.map(([m, privilege]) => (
                  <ListItem key={`${m}-${privilege}`}>
                    <Stack direction="row" sx={{ alignItems: 'center', width: '100%' }} spacing={1}>
                      <HowlerAvatar userId={m || 'Unknown'} />
                      <ListItemText
                        primary={users[m]?.name || m}
                        secondary={
                          users[m]?.email
                            ? `${getPrivilegeLabel(privilege)} - ${users[m].email}`
                            : getPrivilegeLabel(privilege)
                        }
                      />
                      <FlexOne />
                      {privilege !== 'owner' && (
                        <IconButton disabled={!params.id} onClick={() => handleRemoveMember(m, privilege)}>
                          <Delete color="error" />
                        </IconButton>
                      )}
                    </Stack>
                  </ListItem>
                ))}
              </List>
            </Stack>
            <Stack spacing={1}>
              <ToggleButtonGroup
                exclusive
                value={privilege}
                onChange={(_e, _privilege: MemberItem[1]) => setPrivilege(_privilege)}
              >
                {availablePrivileges.map(k => (
                  <ToggleButton key={k} value={k}>
                    {getPrivilegeLabel(k)}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <UserList
                  variant="list"
                  multiple
                  i18nLabel={t('page.login.username')}
                  userIds={selectedUserIds}
                  onChange={setSelectedUserIds}
                  except={members
                    .filter(([_, _privilege]) => _privilege === 'owner' || privilege === _privilege)
                    .map(([member]) => member)}
                />
              </Box>
              <Button
                onClick={handleAddMember}
                sx={{ mt: 3 }}
                variant="contained"
                fullWidth
                disabled={
                  !params.id ||
                  selectedUserIds.length === 0 ||
                  !privilege ||
                  (privilege === 'owner' && selectedUserIds.length > 1)
                }
              >
                {t('add')}
              </Button>
            </Stack>
          </Stack>
        </DialogContent>
      </Dialog>
    </>
  );
};

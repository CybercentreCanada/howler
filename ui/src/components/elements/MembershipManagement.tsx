import { Delete } from '@mui/icons-material';
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
  MenuItem,
  TextField
} from '@mui/material';
import { useAppUser } from '@tui/core';
import api from 'api';
import { UserListContext } from 'components/app/providers/UserListProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import useMyUserList from 'components/hooks/useMyUserList';
import type { Action } from 'models/entities/generated/Action';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { View } from 'models/entities/generated/View';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useParams } from 'react-router';
import HowlerAvatar from './display/HowlerAvatar';
import UserList from './UserList';

type EntityType = 'action' | 'view' | 'dossier';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
}

interface MemberItem {
  user_id: string;
  privilege: 'owner' | 'admins' | 'members';
}

type Entity = Action | Dossier | View;

export const MembershipManagement = ({ open, onClose }: MembershipManagementProps) => {
  const params = useParams();
  const { t } = useTranslation();
  const location = useLocation();
  const { dispatchApi } = useMyApi();
  const appUser = useAppUser<HowlerUser>();
  const { searchUsers } = useContext(UserListContext);
  const { showSuccessMessage, showWarningMessage, showErrorMessage } = useMySnackbar();

  const [members, setMembers] = useState<MemberItem[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [memberQuery, setMemberQuery] = useState('');
  const [privilege, setPrivilege] = useState('');

  const memberUserIds = useMemo(() => new Set(members.map(member => member.user_id)), [members]);
  const users = useMyUserList(memberUserIds);

  const entityType = location.pathname.split('/')[1].replace(/s$/, '') as EntityType;

  const mapEntityToMembers = useCallback((entity: Entity): MemberItem[] => {
    return [
      ...(entity.owner ? [{ user_id: entity.owner, privilege: 'owner' as const }] : []),
      ...(entity.admins ?? []).map(admin => ({ user_id: admin, privilege: 'admins' as const })),
      ...(entity.members ?? []).map(member => ({ user_id: member, privilege: 'members' as const }))
    ];
  }, []);

  const refresh = useCallback(async () => {
    const entity = (
      await dispatchApi(
        api.search[entityType].post({
          query: `${entityType}_id:${params.id}`,
          rows: 1
        }),
        { throwError: false }
      )
    )?.items[0];

    if (!entity) {
      return;
    }

    setMembers(mapEntityToMembers(entity));
  }, [dispatchApi, entityType, mapEntityToMembers, params.id]);

  const handleAddMember = useCallback(async () => {
    if (selectedUserIds.length === 0) {
      showWarningMessage(t('membership.message.warning'));
      return;
    }

    try {
      const updatedEntity: Entity = await dispatchApi(
        api[entityType].permission.put(params.id, {
          privilege,
          user_ids: selectedUserIds
        })
      );

      showSuccessMessage(t('membership.message.success'));

      setMembers(mapEntityToMembers(updatedEntity));

      setSelectedUserIds([]);
      setMemberQuery('');
      setPrivilege('');
    } catch {
      showErrorMessage(t('membership.message.error'));
    }
  }, [
    dispatchApi,
    params.id,
    entityType,
    mapEntityToMembers,
    selectedUserIds,
    privilege,
    t,
    showSuccessMessage,
    showErrorMessage,
    showWarningMessage
  ]);

  // Keep the targeted privilege explicit so we remove the intended permission entry.
  const handleRemoveMember = useCallback(
    async (user_id: string, targetPrivilege: string) => {
      const updatedEntity = (await dispatchApi(
        api[entityType].permission.delete(params.id, {
          privilege: targetPrivilege,
          user_ids: [user_id]
        }),
        {
          throwError: false
        }
      )) as Entity | null;

      if (updatedEntity) {
        setMembers(mapEntityToMembers(updatedEntity));
        return;
      }

      await refresh();
    },
    [dispatchApi, params.id, entityType, mapEntityToMembers, refresh]
  );

  useEffect(() => {
    if (open) {
      // Reset modal state each time it opens to avoid leaking stale UI state.
      void refresh();
      setSelectedUserIds([]);
      setMemberQuery('');
      setPrivilege('');
    }
  }, [open, refresh]);

  useEffect(() => {
    searchUsers('uname:*');
  }, [searchUsers]);

  const currentUser = appUser?.user;
  const canAssignOwner =
    !!currentUser &&
    (currentUser.roles?.includes('admin') ||
      members.some(member => member.privilege === 'owner' && member.user_id === currentUser.username));

  const availablePrivileges: MemberItem['privilege'][] = canAssignOwner
    ? ['owner', 'admins', 'members']
    : ['admins', 'members'];

  const getPrivilegeLabel = useCallback(
    (privilegeValue: MemberItem['privilege']) => {
      return t(`membership.privilege.${privilegeValue}`);
    },
    [t]
  );

  const filteredMembers = useMemo(
    () =>
      members.filter(member => {
        const normalizedQuery = memberQuery.trim().toLowerCase();

        if (!normalizedQuery) {
          return true;
        }

        return (
          member.user_id.includes(normalizedQuery) ||
          member.privilege.includes(normalizedQuery) ||
          getPrivilegeLabel(member.privilege).includes(normalizedQuery)
        );
      }),
    [members, getPrivilegeLabel, memberQuery]
  );

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('membership.manage')}</DialogTitle>
      <DialogContent sx={{ minHeight: '280px', mt: 1 }}>
        <TextField
          fullWidth
          size="small"
          label={t('search')}
          value={memberQuery}
          onChange={event => setMemberQuery(event.target.value)}
          sx={{ mb: 2 }}
        />
        <List>
          {filteredMembers.map(m => (
            <ListItem
              key={`${m.user_id}-${m.privilege}`}
              secondaryAction={
                m.privilege !== 'owner' && (
                  <IconButton disabled={!params.id} onClick={() => handleRemoveMember(m.user_id, m.privilege)}>
                    <Delete color="error" />
                  </IconButton>
                )
              }
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <HowlerAvatar userId={m.user_id || 'Unknown'} />
                <ListItemText
                  primary={users[m.user_id]?.name || m.user_id}
                  secondary={
                    users[m.user_id]?.email
                      ? `${getPrivilegeLabel(m.privilege)} - ${users[m.user_id].email}`
                      : getPrivilegeLabel(m.privilege)
                  }
                />
              </Box>
            </ListItem>
          ))}
        </List>
        <Divider />
        <Box sx={{ mt: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <UserList
              variant="list"
              multiple
              i18nLabel={t('page.login.username')}
              userIds={selectedUserIds}
              onChange={setSelectedUserIds}
            />
          </Box>
          <TextField
            select
            label={t('route.action.privilege.privilege')}
            fullWidth
            value={privilege}
            onChange={e => setPrivilege(e.target.value)}
            sx={{ mt: 2 }}
          >
            {availablePrivileges.map(k => (
              <MenuItem key={k} value={k}>
                {getPrivilegeLabel(k)}
              </MenuItem>
            ))}
          </TextField>
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
        </Box>
      </DialogContent>
    </Dialog>
  );
};

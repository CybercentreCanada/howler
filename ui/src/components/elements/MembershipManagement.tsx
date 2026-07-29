import { Delete } from '@mui/icons-material';
import {
  Alert,
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
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import { UserListContext } from 'components/app/providers/UserListProvider';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserList from 'components/hooks/useMyUserList';
import type { Action } from 'models/entities/generated/Action';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { View } from 'models/entities/generated/View';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useParams } from 'react-router-dom';
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

  const [members, setMembers] = useState<MemberItem[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [memberSearch, setMemberSearch] = useState('');
  const [privilege, setPrivilege] = useState(''); // Used for adding
  const [addResultMessage, setAddResultMessage] = useState<string>('');
  const [addResultSeverity, setAddResultSeverity] = useState<'success' | 'warning'>('success');

  const normalizeUserId = useCallback((value: string) => value.trim().toLowerCase(), []);

  const memberUserIds = useMemo(() => new Set(members.map(member => member.user_id)), [members]);
  const users = useMyUserList(memberUserIds);
  const normalizedSelectedUserIds = useMemo(
    () => Array.from(new Set(selectedUserIds.map(id => id.trim()).filter(Boolean))),
    [selectedUserIds]
  );

  const entityType = location.pathname.split('/')[1].replace(/s$/, '') as EntityType;

  const mapEntityToMembers = useCallback((entity: Entity): MemberItem[] => {
    return [
      ...(entity.owner ? [{ user_id: entity.owner, privilege: 'owner' as const }] : []),
      ...(entity.admins ?? []).map(admin => ({ user_id: admin, privilege: 'admins' as const })),
      ...(entity.members ?? []).map(member => ({ user_id: member, privilege: 'members' as const }))
    ];
  }, []);

  const refresh = useCallback(async (): Promise<MemberItem[]> => {
    if (!params.id) {
      return [];
    }

    const entity = (
      await dispatchApi(
        api.search[entityType].post({
          query: `${entityType}_id:${params.id}`,
          rows: 1
        }),
        { throwError: false }
      )
    )?.items[0];

    if (!entity) return [] as MemberItem[];

    const memberList = mapEntityToMembers(entity);

    setMembers(memberList);

    return memberList;
  }, [dispatchApi, entityType, mapEntityToMembers]);

  const handleAddMember = useCallback(async () => {
    if (!params.id) {
      return;
    }

    if (normalizedSelectedUserIds.length === 0) {
      setAddResultSeverity('warning');
      setAddResultMessage(t('members') + ': ' + t('add') + ' invalid selection');
      return;
    }

    let updatedEntity: Entity | null = null;

    api[entityType].permission.put(params.id, {
      privilege,
      user_id: normalizedSelectedUserIds
    });

    const updatedMembers = updatedEntity ? mapEntityToMembers(updatedEntity) : await refresh();
    if (updatedEntity) {
      setMembers(updatedMembers);
    }

    const memberIdSet = new Set(updatedMembers.map(member => normalizeUserId(member.user_id)));
    const addedUserIds = normalizedSelectedUserIds.filter(user_id => memberIdSet.has(normalizeUserId(user_id)));
    const missingUserIds = normalizedSelectedUserIds.filter(user_id => !memberIdSet.has(normalizeUserId(user_id)));

    if (missingUserIds.length === 0) {
      setAddResultSeverity('success');
      setAddResultMessage(t('members') + ': ' + t('add') + ' OK (' + addedUserIds.join(', ') + ')');
    } else {
      setAddResultSeverity('warning');
      setAddResultMessage(
        t('members') +
          ': ' +
          t('add') +
          ' partial. Added [' +
          addedUserIds.join(', ') +
          '], missing [' +
          missingUserIds.join(', ') +
          ']'
      );
    }

    setSelectedUserIds([]);
    setMemberSearch('');
    setPrivilege('');
  }, [
    dispatchApi,
    params.id,
    entityType,
    mapEntityToMembers,
    normalizeUserId,
    normalizedSelectedUserIds,
    privilege,
    refresh,
    t
  ]);

  // Keep the targeted privilege explicit so we remove the intended permission entry.
  const handleRemoveMember = useCallback(
    async (user_id: string, targetPrivilege: string) => {
      if (!params.id) {
        return;
      }

      const updatedEntity = (await dispatchApi(
        api[entityType].permission.delete(params.id, {
          privilege: targetPrivilege,
          user_id: [user_id]
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
      refresh();
      setSelectedUserIds([]);
      setMemberSearch('');
      setPrivilege('');
      setAddResultMessage('');
    }
  }, [open, refresh]);

  useEffect(() => {
    searchUsers('uname:*');
  }, []);

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
      return t(`route.actions.privilege.${privilegeValue}`);
    },
    [t]
  );

  const filteredMembers = members.filter(member => {
    const query = normalizeUserId(memberSearch);
    if (!query) {
      return true;
    }

    const roleMatches = normalizeUserId(getPrivilegeLabel(member.privilege)).includes(query);

    return (
      normalizeUserId(member.user_id).includes(query) ||
      normalizeUserId(member.privilege).includes(query) ||
      roleMatches
    );
  });

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('route.actions.permission')}</DialogTitle>
      <DialogContent sx={{ minHeight: '280px', mt: 1 }}>
        {!!addResultMessage && (
          <Alert
            severity={addResultSeverity}
            variant={addResultSeverity === 'warning' ? 'outlined' : 'standard'}
            sx={{ mb: 2 }}
          >
            {addResultMessage}
          </Alert>
        )}
        <TextField
          fullWidth
          size="small"
          label={t('search')}
          value={memberSearch}
          onChange={event => setMemberSearch(event.target.value)}
          sx={{ mb: 2 }}
        />
        <List>
          {filteredMembers.map(m => (
            <ListItem
              key={`${m.user_id}-${m.privilege}`}
              secondaryAction={
                m.privilege !== 'owner' && (
                  <IconButton onClick={() => handleRemoveMember(m.user_id, m.privilege)}>
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
              normalizedSelectedUserIds.length === 0 ||
              !privilege ||
              (privilege === 'owner' && normalizedSelectedUserIds.length > 1)
            }
          >
            {t('add')}
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

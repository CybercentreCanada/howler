import { Delete } from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Tab,
  Tabs,
  TextField
} from '@mui/material';
import api from 'api';
import type { PermissionData } from 'api/permission';
import { useAppUser } from 'commons/components/app/hooks';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserList from 'components/hooks/useMyUserList';
import type { Action } from 'models/entities/generated/Action';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { View } from 'models/entities/generated/View';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import HowlerAvatar from './display/HowlerAvatar';
import UserList from './UserList';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
  entityId?: string;
  entityType?: 'action' | 'view' | 'dossier';
  actionId?: string;
}

interface MemberItem {
  user_id: string;
  privilege: 'owner' | 'admins' | 'members';
}

type Entity = Action | Dossier | View;

export const MembershipManagement = ({
  open,
  onClose,
  entityId,
  entityType = 'action',
  actionId
}: MembershipManagementProps) => {
  const translation = useTranslation();
  const { dispatchApi } = useMyApi();
  const appUser = useAppUser<HowlerUser>();
  const finalEntityId = entityId || actionId;

  const [tab, setTab] = useState(0);
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

  const mapEntityToMembers = useCallback((entity: Entity): MemberItem[] => {
    return [
      ...(entity.owner ? [{ user_id: entity.owner, privilege: 'owner' as const }] : []),
      ...(entity.admins ?? []).map(admin => ({ user_id: admin, privilege: 'admins' as const })),
      ...(entity.members ?? []).map(member => ({ user_id: member, privilege: 'members' as const }))
    ];
  }, []);

  const refresh = useCallback(async () => {
    if (!finalEntityId) {
      return [] as MemberItem[];
    }

    // Made for type script compliance, could be done by api[entityType].get(finalEntityId) but Type script complain
    let request;
    switch (entityType) {
      case 'action':
        request = api.action.get(finalEntityId);
        break;
      case 'view':
        request = api.view.get(finalEntityId);
        break;
      case 'dossier':
        request = api.dossier.get(finalEntityId);
        break;
    }

    const entity = (await dispatchApi(request, { throwError: false })) as Entity;

    if (!entity) return [] as MemberItem[];

    const memberList = mapEntityToMembers(entity);
    setMembers(memberList);
    return memberList;
  }, [dispatchApi, finalEntityId, entityType, mapEntityToMembers]);

  const handleAddMember = useCallback(async () => {
    if (!finalEntityId) {
      return;
    }

    if (normalizedSelectedUserIds.length === 0) {
      setAddResultSeverity('warning');
      setAddResultMessage(translation.t('members') + ': ' + translation.t('add') + ' invalid selection');
      return;
    }

    let updatedEntity: Entity | null = null;

    (api[entityType].permission as { put: (id: string, data: PermissionData) => Promise<Entity> }).put(finalEntityId, {
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
      setAddResultMessage(
        translation.t('members') + ': ' + translation.t('add') + ' OK (' + addedUserIds.join(', ') + ')'
      );
    } else {
      setAddResultSeverity('warning');
      setAddResultMessage(
        translation.t('members') +
          ': ' +
          translation.t('add') +
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
    setTab(0);
  }, [
    dispatchApi,
    finalEntityId,
    entityType,
    mapEntityToMembers,
    normalizeUserId,
    normalizedSelectedUserIds,
    privilege,
    refresh,
    translation
  ]);

  // Keep the targeted privilege explicit so we remove the intended permission entry.
  const handleRemoveMember = useCallback(
    async (user_id: string, targetPrivilege: string) => {
      if (!finalEntityId) {
        return;
      }

      const updatedEntity = (await dispatchApi(
        api[entityType].permission.delete(finalEntityId, {
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
    [dispatchApi, finalEntityId, entityType, mapEntityToMembers, refresh]
  );

  useEffect(() => {
    if (open) {
      // Reset modal state each time it opens to avoid leaking stale UI state.
      refresh();
      setTab(0);
      setSelectedUserIds([]);
      setMemberSearch('');
      setPrivilege('');
      setAddResultMessage('');
    }
  }, [open, refresh]);

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
      return translation.t(`route.actions.privilege.${privilegeValue}`);
    },
    [translation]
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
      <DialogTitle>{translation.t('route.actions.permission')}</DialogTitle>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
        <Tab label={translation.t('members')} />
        <Tab label={translation.t('add')} />
      </Tabs>
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
        {tab === 0 ? (
          <>
            <TextField
              fullWidth
              size="small"
              label={translation.t('search')}
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
          </>
        ) : (
          <Box sx={{ mt: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <UserList
                i18nLabel={translation.t('page.login.username')}
                isModified
                allowMultiple
                selectedUserIds={selectedUserIds}
                onChangeSelectedUserIds={setSelectedUserIds}
              />
            </Box>
            <TextField
              select
              label={translation.t('route.action.privilege.privilege')}
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
              {translation.t('add')}
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};

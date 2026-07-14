import { Delete } from '@mui/icons-material';
import {
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
  TextField,
  Typography
} from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Action } from 'models/entities/generated/Action';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { View } from 'models/entities/generated/View';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
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

export const MembershipManagement = ({ open, onClose, entityId, entityType = 'action' }: MembershipManagementProps) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const userPickerContainerRef = useRef<HTMLDivElement | null>(null);

  const openUserPicker = useCallback(() => {
    const button = userPickerContainerRef.current?.querySelector('button');
    button?.click();
  }, []);

  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState(''); // Used for adding

  const refresh = useCallback(async () => {
    if (!entityId) {
      return;
    }

    const entity = (await dispatchApi(api[entityType].get(entityId), { throwError: false })) as Entity;

    if (!entity) return;

    const memberList: MemberItem[] = [
      ...(entity.owner ? [{ user_id: entity.owner, privilege: 'owner' }] : []),
      ...entity.admins.map(admin => ({ user_id: admin, privilege: 'admins' })),
      ...entity.members.map(member => ({ user_id: member, privilege: 'members' }))
    ];
    setMembers(memberList);
  }, [entityId, dispatchApi, entityType]);

  const handleAddMember = useCallback(async () => {
    if (!entityId) {
      return;
    }

    api[entityType].permission.put(entityId, { user_id: username, privilege }).then(() => {
      setUsername('');
      setPrivilege('');
      refresh();
      setTab(0);
    });
  }, [entityId, entityType, privilege, refresh, username]);

  // Keep the targeted privilege explicit so we remove the intended permission entry.
  const handleRemoveMember = useCallback(
    async (user_id: string, targetPrivilege: string) => {
      if (!entityId) {
        return;
      }

      await api[entityType].permission.delete(entityId, { user_id, privilege: targetPrivilege });

      refresh();
    },
    [entityId, entityType, refresh]
  );

  useEffect(() => {
    if (open) {
      // Reset modal state each time it opens to avoid leaking stale UI state.
      refresh();
      setTab(0);
    }
  }, [open, refresh]);

  useEffect(() => {
    if (!open || tab !== 1) {
      return;
    }

    // Auto-open the existing UserList picker so users can type immediately.
    openUserPicker();
  }, [open, tab, openUserPicker]);

  const availablePrivileges: MemberItem['privilege'][] = ['admins', 'members'];

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('route.actions.permission')}</DialogTitle>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
        <Tab label={t('members')} />
        <Tab label={t('add')} />
      </Tabs>
      <DialogContent sx={{ minHeight: '280px', mt: 1 }}>
        {tab === 0 ? (
          <List>
            {members.map(m => (
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
                <ListItemText primary={m.user_id} secondary={m.privilege} />
              </ListItem>
            ))}
          </List>
        ) : (
          <Box sx={{ mt: 1 }}>
            <Box ref={userPickerContainerRef} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <UserList userId={username} onChange={setUsername} i18nLabel="username" />
              <Box
                role="button"
                tabIndex={0}
                onClick={openUserPicker}
                onKeyDown={event => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openUserPicker();
                  }
                }}
                sx={{ cursor: 'pointer' }}
              >
                <Typography variant="caption" color="text.secondary">
                  {t('username')}
                </Typography>
                <Typography variant="body2">{username || '-'}</Typography>
              </Box>
            </Box>
            <TextField
              select
              label={t('privilege')}
              fullWidth
              value={privilege}
              onChange={e => setPrivilege(e.target.value)}
              sx={{ mt: 2 }}
            >
              {availablePrivileges.map(k => (
                <MenuItem key={k} value={k}>
                  {k}
                </MenuItem>
              ))}
            </TextField>
            <Button
              onClick={handleAddMember}
              sx={{ mt: 3 }}
              variant="contained"
              fullWidth
              disabled={!username || !privilege}
            >
              {t('add')}
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};

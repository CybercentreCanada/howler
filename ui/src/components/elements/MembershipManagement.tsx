import { Delete } from '@mui/icons-material';
import {
  Autocomplete,
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
import useMyApi from 'components/hooks/useMyApi';
import type { Action } from 'models/entities/generated/Action';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { View } from 'models/entities/generated/View';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
  entityId?: string;
  entityType?: 'action' | 'view' | 'dossier';
  actionId?: string;
}

interface MemberItem {
  user_id: string;
  privilege: string;
}

type Entity = Action | Dossier | View;

export const MembershipManagement = ({ open, onClose, entityId, entityType = 'action' }: MembershipManagementProps) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState(''); // Used for adding
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasPerformedSearch = useRef(false);

  const refresh = useCallback(async () => {
    if (!entityId) {
      return;
    }

    const entity = (await dispatchApi(api[entityType].get(entityId), { throwError: false })) as Entity;

    if (!entity) return;

    // Normalize backend ownership/admin/member fields into one list for display.
    const memberList: MemberItem[] = [
      ...(entity.owner ? [{ user_id: entity.owner, privilege: 'owner' }] : []),
      ...entity.admins.map(admin => ({ user_id: admin, privilege: 'administrator' })),
      ...entity.members.map(member => ({ user_id: member, privilege: 'member' }))
    ];
    setMembers(memberList);

    try {
      const result = dispatchApi(api[entityType].permission.getOptions(entityId));

      setOptions(result);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error(e);
    }
  }, [entityId, dispatchApi, entityType]);

  const performSearch = useCallback(
    async (query: string) => {
      // Wildcard search is used so partial usernames can be discovered quickly.
      const result = await dispatchApi(api.search.user.post({ query: `name:*${query}*` }), { throwError: false });

      if (result) {
        setUserOptions(result.items);
      }

      hasPerformedSearch.current = true;
    },
    [dispatchApi]
  );

  const handleSearchUsers = useCallback(
    (query: string) => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current);

      if (!query || query.length < 2) {
        setUserOptions([]);
        return;
      }

      if (!hasPerformedSearch.current) {
        // Run the first eligible search immediately to keep the UI responsive.
        performSearch(query);
      } else {
        // Debounce subsequent lookups to reduce backend calls while typing.
        searchTimeout.current = setTimeout(() => performSearch(query), 500);
      }
    },
    [performSearch]
  );

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
      hasPerformedSearch.current = false;
    }
    return () => {
      if (searchTimeout.current) clearTimeout(searchTimeout.current);
    };
  }, [open, refresh]);

  const availablePrivileges = useMemo(() => {
    const keys = Object.keys(options);
    return keys.length > 0 ? keys : ['administrator', 'member'];
  }, [options]);

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
            <Autocomplete
              freeSolo
              options={userOptions}
              getOptionLabel={(o: any) => (typeof o === 'string' ? o : o.uname || o.username || '')}
              onInputChange={(_, v) => {
                handleSearchUsers(v);
                setUsername(v);
              }}
              onChange={(_, v) => setUsername(typeof v === 'string' ? v : v?.uname || v?.username || '')}
              renderInput={p => <TextField {...p} label={t('username')} fullWidth />}
            />
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

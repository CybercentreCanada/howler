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
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
  entityId?: string;
  entityType?: 'action' | 'view' | 'dossier';
  actionId?: string; // Kept for backward compatibility with older components
}

interface MemberItem {
  user_id: string;
  privilege: 'owner' | 'admin' | 'member';
}

/**
 * Utility to safely unwrap nested arrays, strings, or Python stringified objects
 */
const safeUnwrap = (val: any): string => {
  if (val === null || val === undefined) return '';
  if (Array.isArray(val)) return safeUnwrap(val[0]);
  if (typeof val === 'object') return safeUnwrap(val.uname || val.username || val.user_id || JSON.stringify(val));

  let str = String(val).trim();
  while (
    (str.startsWith('[') && str.endsWith(']')) ||
    (str.startsWith("'") && str.endsWith("'")) ||
    (str.startsWith('"') && str.endsWith('"'))
  ) {
    str = str.slice(1, -1).trim();
  }
  return str;
};

export const MembershipManagement = ({
  open,
  onClose,
  entityId,
  entityType = 'action',
  actionId
}: MembershipManagementProps) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  // Tab state: 0 = View/Remove Members, 1 = Add New Member
  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState('');
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  // Consolidate target generic ID or fallback parameter
  const finalEntityId = entityId || actionId;

  // Memoize API routing layer
  const apiService = useMemo(() => {
    if (entityType === 'action') return api.action;
    if (entityType === 'view') return api.view;
    return (api as any).dossier;
  }, [entityType]);

  const refresh = useCallback(() => {
    if (!finalEntityId || !apiService) return;

    // Fetch members list
    dispatchApi((apiService as any).get(finalEntityId)).then((entity: any) => {
      if (!entity) return;

      const owner = safeUnwrap(entity.owner_id || entity.owner);
      const admins = (entity.admins || []).map(safeUnwrap);
      const membersList = (entity.members || []).map(safeUnwrap);

      const memberList: MemberItem[] = [
        ...(owner ? [{ user_id: owner, privilege: 'owner' as const }] : []),
        ...admins.map(m => ({ user_id: m, privilege: 'admin' as const })),
        ...membersList.map(m => ({ user_id: m, privilege: 'member' as const }))
      ];
      setMembers(memberList);
    });

    const permissionService = (apiService as any).permission;
    if (permissionService) {
      const fetchOptions = permissionService.getOptions || permissionService.options;

      if (typeof fetchOptions === 'function') {
        dispatchApi(fetchOptions(finalEntityId))
          .then((res: any) => {
            if (res) setOptions(res);
          })
          .catch(err => {
            // eslint-disable-next-line no-console
            console.error('[MembershipManagement] Failed to fetch permission options:', err);
          });
      }
    }
  }, [finalEntityId, apiService, dispatchApi]);

  useEffect(() => {
    if (open) {
      refresh();
      setTab(0);
    }
  }, [open, refresh]);

  // Handles async user autocomplete suggestions
  const handleSearchUsers = (query: string) => {
    if (!query) {
      setUserOptions([]);
      return;
    }
    const searchService = (api as any).user || (api as any).search?.user;
    if (searchService && typeof searchService.search === 'function') {
      dispatchApi(searchService.search(query)).then((res: any) => {
        setUserOptions(res?.items || res || []);
      });
    }
  };

  const handleAddMember = () => {
    if (!finalEntityId) return;
    (apiService as any).permission.put(finalEntityId, { user_id: username, privilege }).then(() => {
      setUsername('');
      setPrivilege('');
      refresh();
      setTab(0);
    });
  };

  const handleRemoveMember = (user_id: string, priv: string) => {
    if (!finalEntityId) return;
    (apiService as any).permission.delete(finalEntityId, { user_id, privilege: priv }).then(refresh);
  };

  // Fallback protection array: prevents dropdown from being completely blank if option fetch delays
  const availablePrivileges = useMemo(() => {
    const keys = Object.keys(options);
    return keys.length > 0 ? keys : ['admin', 'member'];
  }, [options]);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('membership.management')}</DialogTitle>

      <Tabs
        value={tab}
        onChange={(_, newTab) => setTab(newTab)}
        variant="fullWidth"
        indicatorColor="primary"
        textColor="primary"
      >
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
                <ListItemText primary={m.user_id} secondary={t(`privilege.${m.privilege}`, m.privilege)} />
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
              onChange={(_, v) => {
                const selectedUser = typeof v === 'string' ? v : v?.uname || v?.username || '';
                setUsername(selectedUser);
              }}
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
                  {t(`privilege.${k}`, k)}
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

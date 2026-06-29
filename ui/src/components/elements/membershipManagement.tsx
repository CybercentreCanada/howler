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

  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState(''); // Used for adding
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasPerformedSearch = useRef(false);

  const finalEntityId = entityId || actionId;

  const apiService = useMemo(
    () => (entityType === 'action' ? api.action : entityType === 'view' ? api.view : (api as any).dossier),
    [entityType]
  );

  const refresh = useCallback(() => {
    if (!finalEntityId || !apiService) return;

    dispatchApi((apiService as any).get(finalEntityId)).then((entity: any) => {
      if (!entity) return;

      const owner = safeUnwrap(entity.owner_id || entity.owner);
      const adminUsers: any[] = entity.admins || entity.administrator || [];
      const adminRoleLabel = 'administrator';
      const membersList = (entity.members || []).map(safeUnwrap);

      const memberList: MemberItem[] = [
        ...(owner ? [{ user_id: owner, privilege: 'owner' }] : []),
        ...adminUsers.map(m => ({ user_id: safeUnwrap(m), privilege: adminRoleLabel })),
        ...membersList.map(m => ({ user_id: m, privilege: 'member' }))
      ];
      setMembers(memberList);
    });

    const permissionService = (apiService as any).permission;
    if (permissionService?.getOptions) {
      dispatchApi(permissionService.getOptions(finalEntityId))
        .then((res: any) => res && setOptions(res))
        .catch(console.error);
    }
  }, [finalEntityId, apiService, dispatchApi]);

  const performSearch = (query: string) => {
    const searchService = (api as any).user || (api as any).search?.user;
    if (searchService?.search) {
      dispatchApi(searchService.search(query)).then((res: any) => {
        setUserOptions(res?.items || res || []);
        hasPerformedSearch.current = true;
      });
    }
  };

  const handleSearchUsers = (query: string) => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);

    if (!query || query.length < 2) {
      setUserOptions([]);
      return;
    }

    if (!hasPerformedSearch.current) {
      performSearch(query);
    } else {
      searchTimeout.current = setTimeout(() => performSearch(query), 500);
    }
  };

  const handleAddMember = () => {
    if (!finalEntityId || !(apiService as any).permission) return;
    (apiService as any).permission.put(finalEntityId, { user_id: username, privilege }).then(() => {
      setUsername('');
      setPrivilege('');
      refresh();
      setTab(0);
    });
  };

  // Fixed: Renamed parameter to 'targetPrivilege' to avoid scope conflict
  const handleRemoveMember = (user_id: string, targetPrivilege: string) => {
    if (!finalEntityId || !(apiService as any).permission) return;
    (apiService as any).permission.delete(finalEntityId, { user_id, privilege: targetPrivilege }).then(refresh);
  };

  useEffect(() => {
    if (open) {
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

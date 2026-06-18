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
import { useAppUser } from 'commons/components/app/hooks';
import useMyApi from 'components/hooks/useMyApi';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
  actionId: string;
}

interface MemberItem {
  user_id: string;
  privilege: 'owner' | 'admin' | 'member';
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

export const MembershipManagement = ({ open, onClose, actionId }: MembershipManagementProps) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { user } = useAppUser<HowlerUser>();

  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [actionOwner, setActionOwner] = useState<string>('');
  const [actionAdmins, setActionAdmins] = useState<string[]>([]);
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState('');
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  const refresh = useCallback(() => {
    dispatchApi(api.action.get(actionId)).then(action => {
      if (!action) return;

      const owner = safeUnwrap(action.owner_id);
      const admins = (action.admins || []).map(safeUnwrap);
      const membersList = (action.members || []).map(safeUnwrap);

      setActionOwner(owner);
      setActionAdmins(admins);

      const memberList: MemberItem[] = [
        ...(owner ? [{ user_id: owner, privilege: 'owner' as const }] : []),
        ...admins.map(m => ({ user_id: m, privilege: 'admin' as const })),
        ...membersList.map(m => ({ user_id: m, privilege: 'member' as const }))
      ];
      setMembers(memberList);
    });

    dispatchApi(api.action.permission.getOptions(actionId)).then(setOptions);
  }, [actionId, dispatchApi]);

  useEffect(() => {
    if (open && actionId) refresh();
  }, [open, actionId, refresh]);

  // UPDATE THIS IF ANY NEW PERMISSION IS ADDED. THIS IS FOR TRANSLATION
  const getPrivilegeLabel = (priv: string) => {
    if (priv === 'owner' || priv === 'admin' || priv === 'member') {
      return t(`route.actions.privilege.${priv}`);
    }
    return priv;
  };

  const handleSearchUsers = async (query: string) => {
    if (query.length === 1) return;
    const results = await dispatchApi(api.user.search(query));
    setUserOptions(results || []);
  };

  const handleAddMember = async () => {
    if (!username || !privilege) return;

    await dispatchApi(
      api.action.permission.put(actionId, {
        privilege: privilege,
        user_id: username
      })
    );

    setUsername('');
    setPrivilege('');
    setTab(0);
    refresh();
  };

  const handleRemoveMember = async (userId: string, priv: string) => {
    // FIX: Map internal 'admin' to API expected 'administrator'
    const apiPrivilege = priv === 'admin' ? 'administrator' : priv;

    await dispatchApi(
      api.action.permission.delete(actionId, {
        privilege: apiPrivilege,
        user_id: userId,
        is_adding: false
      })
    );
    refresh();
  };

  const isOwner = actionOwner === user.username;
  const isAdmin = actionAdmins.includes(user.username);
  const isSystemAdmin = user.roles?.includes('admin');
  const canManage = isOwner || isAdmin || isSystemAdmin;

  const canDeleteUser = (targetPrivilege: string) => {
    if (targetPrivilege === 'owner') return false;
    return canManage;
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('route.actions.permission')}</DialogTitle>

      {canManage ? (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
          <Tab label="Members" />
          <Tab label="Add" />
        </Tabs>
      ) : (
        <Tabs value={0} variant="fullWidth">
          <Tab label="Members" />
        </Tabs>
      )}

      <DialogContent>
        {tab === 0 || !canManage ? (
          <List>
            {members.map((m, i) => (
              <ListItem
                key={i}
                secondaryAction={
                  canDeleteUser(m.privilege) && (
                    <IconButton onClick={() => handleRemoveMember(m.user_id, m.privilege)}>
                      <Delete color="error" />
                    </IconButton>
                  )
                }
              >
                <ListItemText
                  primary={m.user_id}
                  secondary={getPrivilegeLabel(m.privilege)} // Use the helper here
                />
              </ListItem>
            ))}
          </List>
        ) : (
          <Box sx={{ mt: 2 }}>
            <Autocomplete
              freeSolo
              options={userOptions}
              getOptionLabel={(o: any) => (typeof o === 'string' ? o : o.uname || '')}
              onInputChange={(_, v) => {
                handleSearchUsers(v);
                setUsername(v);
              }}
              onChange={(_, v) => {
                const finalUsername = typeof v === 'string' ? v : v?.uname || '';
                setUsername(finalUsername);
              }}
              renderInput={p => <TextField {...p} label="Username" fullWidth value={username} />}
            />
            <TextField
              select
              label="Privilege"
              fullWidth
              value={privilege}
              onChange={e => setPrivilege(e.target.value)}
              sx={{ mt: 2 }}
            >
              {Object.keys(options).map(k => (
                <MenuItem key={k} value={k}>
                  {k}
                </MenuItem>
              ))}
            </TextField>
            <Button
              onClick={handleAddMember}
              sx={{ mt: 2 }}
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

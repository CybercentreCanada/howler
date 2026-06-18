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

/**
 * use to sanitize username in case the backend returns it in various formats (e.g., direct string, object with different
 * keys, array of one element,
 */
const safeUnwrap = (val: any): string => {
  if (val === null || val === undefined) return '';

  if (Array.isArray(val)) {
    return safeUnwrap(val[0]);
  }

  if (typeof val === 'object') {
    return safeUnwrap(val.uname || val.username || val.user_id || JSON.stringify(val));
  }

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

  const [tab, setTab] = useState(0);
  const [members, setMembers] = useState<MemberItem[]>([]);

  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState('');
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  const refresh = useCallback(() => {
    dispatchApi(api.action.get(actionId)).then(action => {
      if (!action) return;

      const memberList: MemberItem[] = [
        ...(action.owner_id ? [{ user_id: safeUnwrap(action.owner_id), privilege: 'owner' as const }] : []),
        ...(action.admins || []).map(m => ({
          user_id: safeUnwrap(m),
          privilege: 'admin' as const
        })),
        ...(action.members || []).map(m => ({
          user_id: safeUnwrap(m),
          privilege: 'member' as const
        }))
      ];
      setMembers(memberList);
    });
    dispatchApi(api.action.permission.getOptions(actionId)).then(setOptions);
  }, [actionId, dispatchApi]);

  useEffect(() => {
    if (open && actionId) refresh();
  }, [open, actionId, refresh]);

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
    onClose();
  };

  const handleRemoveMember = async (userId: string, priv: string) => {
    await dispatchApi(
      api.action.permission.delete(actionId, {
        privilege: priv,
        user_id: userId,
        is_adding: false
      })
    );
    refresh();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t('route.actions.permission')}</DialogTitle>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
        <Tab label="Members" />
        <Tab label="Add" />
      </Tabs>

      <DialogContent>
        {tab === 0 ? (
          <List>
            {members.map((m, i) => (
              <ListItem
                key={i}
                secondaryAction={
                  m.privilege !== 'owner' &&
                  m.privilege !== 'admin' && (
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
          <Box sx={{ mt: 2 }}>
            <Autocomplete
              options={userOptions}
              getOptionLabel={(o: any) => o.uname || o}
              onInputChange={(_, v) => handleSearchUsers(v)}
              onChange={(_, v) => setUsername(v?.uname || v || '')}
              renderInput={p => <TextField {...p} label="Username" fullWidth />}
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

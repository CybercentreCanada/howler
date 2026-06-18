import { Autocomplete, Button, Dialog, DialogContent, DialogTitle, MenuItem, TextField } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface MembershipManagementProps {
  open: boolean;
  onClose: () => void;
  actionId: string;
}

export const MembershipManagement = ({ open, onClose, actionId }: MembershipManagementProps) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const [username, setUsername] = useState('');
  const [privilege, setPrivilege] = useState('');
  const [options, setOptions] = useState<Record<string, any>>({});
  const [userOptions, setUserOptions] = useState<any[]>([]);

  useEffect(() => {
    if (open && actionId) {
      dispatchApi(api.action.permission.getOptions(actionId)).then(setOptions);
    }
  }, [open, actionId, dispatchApi]);

  const handleSearchUsers = async (query: string) => {
    if (query.length === 1) return;
    const results = await dispatchApi(api.user.search(query));
    setUserOptions(results || []);
  };

  const handleAddMember = async () => {
    await dispatchApi(
      api.action.permission.put(actionId, {
        privilege: privilege,
        user_id: username
      })
    );
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>{t('route.actions.permission')}</DialogTitle>
      <DialogContent>
        <Autocomplete
          options={userOptions}
          getOptionLabel={(option: any) => option.uname || option}
          onInputChange={(_, newInputValue) => handleSearchUsers(newInputValue)}
          onChange={(_, newValue) => setUsername(newValue?.uname || newValue || '')}
          renderInput={params => <TextField {...params} label="Username" fullWidth sx={{ mt: 2 }} />}
        />

        <TextField
          select
          label="Privilege"
          fullWidth
          value={privilege}
          onChange={e => setPrivilege(e.target.value)}
          sx={{ mt: 2 }}
        >
          {Object.keys(options).map(key => (
            <MenuItem key={key} value={key}>
              {key}
            </MenuItem>
          ))}
        </TextField>

        <Button onClick={handleAddMember} sx={{ mt: 2 }} variant="contained">
          {t('add')}
        </Button>
      </DialogContent>
    </Dialog>
  );
};

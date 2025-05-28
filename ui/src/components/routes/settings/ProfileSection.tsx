import { Add, Check, ChevronRight, Clear } from '@mui/icons-material';
import { Chip, CircularProgress, Grid, TableCell, TableRow, Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useCallback, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { delay } from 'utils/utils';
import EditRow from '../../elements/EditRow';
import SettingsSection from './SettingsSection';

const ProfileSection: FC<{
  user: HowlerUser;
  editName?: (value: string) => Promise<void>;
  addRole?: (role: string) => Promise<void>;
  removeRole?: (role: string) => Promise<void>;
  viewGroups: () => Promise<void>;
}> = ({ user, editName, addRole, removeRole, viewGroups }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [loadingGroups, setLoadingGroups] = useState(false);

  const wrapChange = useCallback(
    async (r: string, fn: (arg: string) => Promise<void>) => {
      const delayedLoad = delay(250);

      delayedLoad.then(() => {
        setLoading({
          ...loading,
          [r]: true
        });
      });

      try {
        await fn(r);
      } finally {
        delayedLoad.cancel();
        setLoading({
          ...loading,
          [r]: false
        });
      }
    },
    [loading]
  );

  const onViewGroups = useCallback(async () => {
    setLoadingGroups(true);
    try {
      await viewGroups();
    } finally {
      setLoadingGroups(false);
    }
  }, [viewGroups]);

  return (
    <SettingsSection title={t('page.settings.profile.title')} colSpan={3}>
      <TableRow>
        <TableCell style={{ whiteSpace: 'nowrap' }}>{t('page.settings.profile.table.username')}</TableCell>
        <TableCell width="100%" colSpan={2}>
          {user?.username}
        </TableCell>
      </TableRow>
      <EditRow titleKey="page.settings.profile.table.name" value={user?.name} onEdit={editName} />
      <TableRow>
        <TableCell style={{ whiteSpace: 'nowrap' }}>{t('page.settings.profile.table.email')}</TableCell>
        <TableCell width="100%" colSpan={2}>
          {user?.email}
        </TableCell>
      </TableRow>
      {viewGroups && (
        <>
          <TableRow
            onClick={onViewGroups}
            sx={theme => ({
              cursor: 'pointer',
              transitionProperty: 'background-color',
              transitionDuration: theme.transitions.duration.shortest + 'ms',
              '&:hover': { backgroundColor: 'rgba(128, 128, 128, 0.25)' }
            })}
          >
            <TableCell sx={{ borderBottom: 0 }} style={{ whiteSpace: 'nowrap' }}>
              {t('page.settings.profile.table.groups')}
            </TableCell>
            <TableCell sx={{ borderBottom: 0 }} align="right" width="100%" colSpan={2}>
              {loadingGroups ? <CircularProgress size={20} /> : <ChevronRight fontSize="small" />}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell colSpan={3} sx={{ paddingTop: '0 !important' }}>
              <Typography variant="caption" color="text.secondary">
                {t('page.settings.profile.table.groups.description')}
              </Typography>
            </TableCell>
          </TableRow>
        </>
      )}
      <TableRow>
        <TableCell style={{ whiteSpace: 'nowrap' }}>{t('page.settings.profile.table.roles')}</TableCell>
        <TableCell width="100%" colSpan={2}>
          <Grid container direction="row" spacing={1}>
            {config?.lookups?.roles?.map((r: string) => (
              <Grid item key={r}>
                <Chip
                  label={r.toLocaleLowerCase()}
                  color={user?.roles?.includes(r) ? 'primary' : 'default'}
                  icon={
                    loading[r] ? (
                      <CircularProgress size={24} />
                    ) : addRole && !user?.roles?.includes(r) ? (
                      <Add />
                    ) : user?.roles?.includes(r) ? (
                      removeRole ? null : (
                        <Check />
                      )
                    ) : (
                      <Clear />
                    )
                  }
                  onClick={addRole && !user?.roles?.includes(r) ? () => wrapChange(r, addRole) : null}
                  onDelete={removeRole && user?.roles?.includes(r) ? () => wrapChange(r, removeRole) : null}
                />
              </Grid>
            ))}
          </Grid>
        </TableCell>
      </TableRow>
    </SettingsSection>
  );
};

export default ProfileSection;

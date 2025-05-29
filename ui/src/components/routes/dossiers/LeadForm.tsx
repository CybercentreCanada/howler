import { Icon } from '@iconify/react/dist/iconify.js';
import { Add } from '@mui/icons-material';
import { Alert, Button, Paper, Stack, Tab, Tabs } from '@mui/material';
import isNull from 'lodash-es/isNull';
import merge from 'lodash-es/merge';
import type { Dossier } from 'models/entities/generated/Dossier';
import { useState, type Dispatch, type FC, type SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import LeadEditor from './LeadEditor';

const LeadForm: FC<{ dossier: Dossier; setDossier: Dispatch<SetStateAction<Partial<Dossier>>>; loading: boolean }> = ({
  dossier,
  setDossier,
  loading
}) => {
  const { t, i18n } = useTranslation();

  const [tab, setTab] = useState(0);

  return (
    <Paper sx={{ p: 1, display: 'flex', flexDirection: 'column', flex: 1 }}>
      <Stack direction="row">
        {!dossier?.leads || dossier.leads.length < 1 ? (
          <Alert
            variant="outlined"
            severity="warning"
            sx={{
              mr: 1,
              px: 1,
              py: 0,
              minHeight: '0 !important',
              display: 'flex',
              alignItems: 'center',
              '& .MuiAlert-icon ': {
                fontSize: '20px',
                py: 0
              },
              '& .MuiAlert-message': {
                py: 0.7
              }
            }}
          >
            {t('route.dossiers.manager.lead.create')}
          </Alert>
        ) : (
          <Tabs value={tab} onChange={(_, _tab) => setTab(_tab)} sx={{ minHeight: '0 !important' }}>
            {dossier.leads?.map((lead, index) => (
              <Tab
                disabled={!dossier || loading}
                sx={{ py: 1, minHeight: '0 !important' }}
                key={lead.content}
                label={
                  <Stack direction="row" spacing={0.5}>
                    {lead.icon && <Icon icon={lead.icon} />}
                    <span>{i18n.language === 'en' ? lead.label.en : lead.label.fr}</span>
                  </Stack>
                }
                value={index}
              />
            ))}
          </Tabs>
        )}
        <Button
          sx={{ ml: 'auto', alignSelf: 'end', minWidth: '0 !important' }}
          size="small"
          variant="contained"
          onClick={() => {
            setTab(dossier.leads?.length ?? 0);
            setDossier(_dossier => ({
              ..._dossier,
              leads: [
                ...(_dossier.leads ?? []),
                { icon: 'material-symbols:add-ad', label: { en: 'New Lead', fr: 'Nouvelle Piste' } }
              ]
            }));
          }}
        >
          <Add />
        </Button>
      </Stack>
      <LeadEditor
        lead={(dossier.leads ?? [])[tab]}
        update={data =>
          setDossier(_dossier => ({
            ..._dossier,
            leads: (_dossier.leads ?? [])
              .map((lead, index) => {
                if (index !== tab) {
                  return lead;
                }

                if (isNull(data)) {
                  return null;
                }

                return merge({}, lead, data);
              })
              .filter(_lead => !isNull(_lead))
          }))
        }
      />
    </Paper>
  );
};

export default LeadForm;

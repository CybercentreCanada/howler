import { Icon, iconExists } from '@iconify/react/dist/iconify.js';
import { Add, Delete, OpenInNew, Remove } from '@mui/icons-material';
import {
  Alert,
  Autocomplete,
  Button,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
  useTheme
} from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import isNull from 'lodash-es/isNull';
import merge from 'lodash-es/merge';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Pivot } from 'models/entities/generated/Pivot';
import howlerPluginStore from 'plugins/store';
import {
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type FC,
  type SetStateAction
} from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useSearchParams } from 'react-router-dom';

export interface PivotFormProps {
  pivot: Pivot;
  update: (pivot: Partial<Pivot>) => void;
}

const LinkForm: FC<PivotFormProps> = ({ pivot, update }) => {
  const { t } = useTranslation();

  const { config } = useContext(ApiConfigContext);

  return (
    <>
      <TextField
        size="small"
        label={t('route.dossiers.manager.pivot.value')}
        disabled={!pivot}
        value={pivot?.value ?? ''}
        fullWidth
        onChange={ev => update({ value: ev.target.value })}
      />
      <Divider flexItem />
      <Typography>{t('route.dossiers.manager.pivot.mappings')}</Typography>
      {pivot?.mappings?.map((_mapping, index) => (
        // eslint-disable-next-line react/no-array-index-key
        <Fragment key={index}>
          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.mapping.key')}
              disabled={!pivot}
              value={_mapping?.key ?? ''}
              onChange={ev =>
                update({
                  mappings: pivot.mappings.map((_m, _index) =>
                    index === _index ? { ..._m, key: ev.target.value } : _m
                  )
                })
              }
            />
            <Autocomplete
              fullWidth
              disabled={!pivot}
              options={['custom', ...Object.keys(config.indexes.hit)]}
              renderInput={params => (
                <TextField
                  {...params}
                  size="small"
                  fullWidth
                  label={t('route.dossiers.manager.pivot.mapping.field')}
                  sx={{ minWidth: '150px' }}
                />
              )}
              getOptionLabel={opt => t(opt)}
              value={_mapping.field ?? ''}
              onChange={(_ev, field) =>
                update({
                  mappings: pivot.mappings.map((_m, _index) => (index === _index ? { ..._m, field } : _m))
                })
              }
            />
            <IconButton
              onClick={() =>
                update({
                  mappings: pivot.mappings.filter((_m, _index) => index !== _index)
                })
              }
            >
              <Remove />
            </IconButton>
          </Stack>
          {_mapping.field === 'custom' && (
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.mapping.custom')}
              disabled={!pivot}
              value={_mapping?.custom_value ?? ''}
              onChange={ev =>
                update({
                  mappings: pivot.mappings.map((_m, _index) =>
                    index === _index ? { ..._m, custom_value: ev.target.value } : _m
                  )
                })
              }
            />
          )}
        </Fragment>
      ))}
      <Button
        id="add-pivot"
        disabled={!pivot}
        sx={{ ml: 'auto', alignSelf: 'end', minWidth: '0 !important' }}
        size="small"
        variant="contained"
        onClick={() => {
          update({
            mappings: [...(pivot.mappings ?? []), { key: 'key' }]
          });
        }}
      >
        <Add />
      </Button>
    </>
  );
};

const PivotForm: FC<{ dossier: Dossier; setDossier: Dispatch<SetStateAction<Partial<Dossier>>>; loading: boolean }> = ({
  dossier,
  setDossier,
  loading
}) => {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const pluginStore = usePluginStore();
  const [searchParams, setSearchParams] = useSearchParams();

  const [tab, setTab] = useState(parseInt(searchParams.get('pivot') ?? '0'));

  const update = useCallback(
    (data: Partial<Pivot>) =>
      setDossier(_dossier => ({
        ..._dossier,
        pivots: (_dossier.pivots ?? [])
          .map((pivot, _index) => {
            if (tab !== _index) {
              return pivot;
            }

            if (isNull(data)) {
              return null;
            }

            const merged = merge({}, pivot, data);

            if (data.mappings) {
              merged.mappings = data.mappings;
            }

            return merged;
          })
          .filter(_pivot => !isNull(_pivot))
      })),
    [setDossier, tab]
  );

  const pivot: Pivot = useMemo(() => dossier.pivots?.[tab] ?? null, [dossier.pivots, tab]);
  const icon = useMemo(() => pivot?.icon ?? 'material-symbols:find-in-page', [pivot?.icon]);

  useEffect(() => {
    searchParams.delete('lead');
    if (searchParams.get('pivot') !== tab.toString()) {
      searchParams.set('pivot', tab.toString());
    }

    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams, tab]);

  return (
    <Paper sx={{ p: 1, display: 'flex', flexDirection: 'column', flex: 1 }} id="pivot-form">
      <Stack spacing={2}>
        <Stack direction="row">
          {!dossier?.pivots || dossier.pivots.length < 1 ? (
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
              {t('route.dossiers.manager.pivot.create')}
            </Alert>
          ) : (
            <Tabs value={tab} onChange={(_, _tab) => setTab(_tab)} sx={{ minHeight: '0 !important' }}>
              {dossier.pivots?.map((lead, index) => (
                <Tab
                  disabled={!dossier || loading}
                  sx={{ py: 1, minHeight: '0 !important' }}
                  key={lead.value}
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
              setTab(dossier.pivots?.length ?? 0);
              setDossier(_dossier => ({
                ..._dossier,
                pivots: [
                  ...(_dossier.pivots ?? []),
                  { icon: 'material-symbols:add-ad', label: { en: 'New Pivot', fr: 'Nouvelle pivot' } }
                ]
              }));
            }}
            disabled={!dossier || loading}
          >
            <Add />
          </Button>
        </Stack>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="center" position="relative">
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.icon')}
              value={icon}
              disabled={!pivot}
              fullWidth
              error={!iconExists(icon)}
              sx={{ '& input': { paddingLeft: '2.25rem' } }}
              onChange={ev => update({ icon: ev.target.value })}
            />
            <Icon fontSize="1.75rem" icon={icon} style={{ position: 'absolute', left: '0.5rem' }} />
            <Button
              variant="outlined"
              color="error"
              disabled={!pivot}
              sx={{ minWidth: '0 !important', ml: 1 }}
              onClick={() => update(null)}
            >
              <Delete />
            </Button>
          </Stack>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: `${theme.spacing(0.5)} !important` }}>
            <Typography color="text.secondary">{t('route.dossiers.manager.icon.description')}</Typography>
            <IconButton size="small" component="a" href="https://icon-sets.iconify.design/">
              <OpenInNew fontSize="small" />
            </IconButton>
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.label.en')}
              disabled={!pivot}
              value={pivot?.label?.en ?? ''}
              fullWidth
              onChange={ev => update({ label: { en: ev.target.value } })}
            />
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.label.fr')}
              disabled={!pivot}
              value={pivot?.label?.fr ?? ''}
              fullWidth
              onChange={ev => update({ label: { fr: ev.target.value } })}
            />
          </Stack>
          <Autocomplete
            disabled={!pivot}
            options={['link', ...howlerPluginStore.pivotFormats]}
            renderInput={params => (
              <TextField {...params} size="small" label={t('route.dossiers.manager.pivot.format')} />
            )}
            value={pivot?.format ?? ''}
            onChange={(_ev, format) => update({ format, value: '', mappings: [] })}
          />
          {!!pivot?.format &&
            (pivot.format === 'link' ? (
              <LinkForm pivot={pivot} update={update} />
            ) : (
              pluginStore.executeFunction(`pivot.${pivot.format}.form`, { pivot, update })
            ))}
        </Stack>
      </Stack>
    </Paper>
  );
};

export default PivotForm;

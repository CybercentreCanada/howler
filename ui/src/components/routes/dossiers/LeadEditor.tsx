import { Icon, iconExists } from '@iconify/react/dist/iconify.js';
import { useMonaco } from '@monaco-editor/react';
import { Delete, OpenInNew } from '@mui/icons-material';
import { Autocomplete, Button, IconButton, Stack, TextField, Typography, useTheme } from '@mui/material';
import ThemedEditor from 'components/elements/ThemedEditor';
import { merge } from 'lodash-es';
import type { Lead } from 'models/entities/generated/Lead';
import howlerPluginStore from 'plugins/store';
import { useCallback, useEffect, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';

export interface LeadFormProps {
  lead?: Lead;
  metadata?: any;
  update: (lead: Partial<Lead>) => void;
  updateMetadata: (data: any) => void;
}

const LeadEditor: FC<{ lead?: Lead; update: (lead: Partial<Lead>) => void }> = ({ lead, update }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const monaco = useMonaco();
  const pluginStore = usePluginStore();

  const icon = useMemo(() => lead?.icon ?? 'material-symbols:find-in-page', [lead?.icon]);
  const metadata = useMemo(() => JSON.parse(lead?.metadata ?? '{}'), [lead?.metadata]);

  const updateMetadata = useCallback(
    _metadata => {
      update({ metadata: JSON.stringify(merge({}, metadata, _metadata)) });
    },
    [metadata, update]
  );

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.getModels().forEach(model => model.setEOL(monaco.editor.EndOfLineSequence.LF));
  }, [monaco]);

  return (
    <Stack spacing={2} pt={2} sx={{ flex: 1 }} id="lead-editor">
      <Stack direction="row" alignItems="center" position="relative">
        <TextField
          size="small"
          label={t('route.dossiers.manager.icon')}
          value={icon}
          disabled={!lead}
          fullWidth
          error={!iconExists(icon)}
          sx={{ '& input': { paddingLeft: '2.25rem' } }}
          onChange={ev => update({ icon: ev.target.value })}
        />
        <Icon fontSize="1.75rem" icon={icon} style={{ position: 'absolute', left: '0.5rem' }} />
        <Button
          variant="outlined"
          color="error"
          disabled={!lead}
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
          label={t('route.dossiers.manager.label.en')}
          disabled={!lead}
          value={lead?.label?.en ?? ''}
          fullWidth
          onChange={ev => update({ label: { en: ev.target.value } })}
        />
        <TextField
          size="small"
          label={t('route.dossiers.manager.label.fr')}
          disabled={!lead}
          value={lead?.label?.fr ?? ''}
          fullWidth
          onChange={ev => update({ label: { fr: ev.target.value } })}
        />
      </Stack>
      <Autocomplete
        disabled={!lead}
        options={['markdown', ...howlerPluginStore.leadFormats]}
        id="lead-format"
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.format')} />}
        value={lead?.format ?? null}
        onChange={(_ev, format) => update({ format, metadata: '{}', content: '' })}
      />
      {!!lead?.format &&
        (lead.format === 'markdown' ? (
          <ThemedEditor
            id="lead-markdown"
            height="100%"
            width="100%"
            language="markdown"
            theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
            value={lead?.content ?? ''}
            onChange={content => update({ content })}
            options={{}}
          />
        ) : (
          pluginStore.executeFunction(`lead.${lead.format}.form`, {
            lead,
            metadata,
            update,
            updateMetadata
          } as LeadFormProps)
        ))}
    </Stack>
  );
};

export default LeadEditor;

import { Icon, iconExists } from '@iconify/react/dist/iconify.js';
import { useMonaco } from '@monaco-editor/react';
import { Delete, OpenInNew } from '@mui/icons-material';
import { Autocomplete, Button, IconButton, Stack, TextField, Typography, useTheme } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import ThemedEditor from 'components/elements/ThemedEditor';
import type { Lead } from 'models/entities/generated/Lead';
import { useContext, useEffect, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

// todo: figure out a way to make this list of formats dynamic
const FORMATS = ['markdown', 'borealis'];

const LeadEditor: FC<{ lead?: Lead; update: (lead: Partial<Lead>) => void }> = ({ lead, update }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const monaco = useMonaco();
  const { config } = useContext(ApiConfigContext);

  const icon = useMemo(() => lead?.icon ?? 'material-symbols:find-in-page', [lead?.icon]);
  // const metadata = useMemo(() => JSON.parse(lead?.metadata ?? '{}'), [lead?.metadata]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    monaco.editor.getModels().forEach(model => model.setEOL(monaco.editor.EndOfLineSequence.LF));
  }, [monaco]);

  return (
    <Stack spacing={2} pt={2} sx={{ flex: 1 }}>
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
        options={FORMATS.filter(value => value !== 'borealis' || config?.configuration?.features?.borealis)}
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.format')} />}
        value={lead?.format ?? ''}
        onChange={(_ev, format) => update({ format, metadata: '{}', content: '' })}
      />
      <ThemedEditor
        height="100%"
        width="100%"
        language={lead?.format === 'markdown' ? 'markdown' : 'text'}
        theme={theme.palette.mode === 'light' ? 'howler' : 'howler-dark'}
        value={lead?.content ?? ''}
        onChange={content => update({ content })}
        options={{}}
      />
    </Stack>
  );
};

export default LeadEditor;

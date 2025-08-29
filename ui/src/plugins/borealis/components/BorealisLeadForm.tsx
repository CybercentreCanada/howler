import { Autocomplete, Divider, ListItemText, TextField, Typography } from '@mui/material';
import { useBorealisEnrichSelector, useBorealisFetcherSelector } from 'borealis-ui';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { LeadFormProps } from 'components/routes/dossiers/LeadEditor';
import { useContext, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const BorealisLeadForm: FC<LeadFormProps> = ({ lead, metadata, update, updateMetadata }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const fetchers = useBorealisFetcherSelector(ctx => ctx.fetchers);
  const types = useBorealisEnrichSelector(ctx => ctx.typesDetection);

  const [showCustom, setShowCustom] = useState(false);

  return (
    <>
      <Divider orientation="horizontal" />
      <Autocomplete
        disabled={!lead}
        options={Object.keys(fetchers)}
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.borealis')} />}
        value={Object.keys(fetchers).includes(lead?.content) ? lead.content : ''}
        onChange={(_ev, content) => update({ content, metadata: '{}' })}
        renderOption={(props, option) => (
          <ListItemText
            {...(props as any)}
            sx={{ flexDirection: 'column', alignItems: 'start !important' }}
            primary={<code>{option}</code>}
            secondary={fetchers[option].description}
          />
        )}
      />
      <Autocomplete
        options={Object.keys(types)}
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.borealis.type')} />}
        value={metadata?.type ?? ''}
        onChange={(_ev, type) => updateMetadata({ type })}
      />
      <Autocomplete
        options={['custom', ...Object.keys(config.indexes.hit)]}
        disabled={!metadata?.type || !types[metadata.type]}
        renderInput={params => (
          <TextField {...params} size="small" label={t('route.dossiers.manager.borealis.value')} />
        )}
        getOptionLabel={opt => t(opt)}
        value={metadata?.value ?? ''}
        onChange={(_ev, value) => {
          if (value === 'custom') {
            setShowCustom(true);
          } else {
            setShowCustom(false);
            updateMetadata({ value });
          }
        }}
      />
      {showCustom && (
        <>
          <TextField
            size="small"
            label={t('route.dossiers.manager.borealis.value.custom')}
            value={metadata?.value ?? ''}
            disabled={!metadata?.type || !types[metadata.type]}
            fullWidth
            onChange={ev => updateMetadata({ value: ev.target.value })}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: '0 !important' }}>
            {t('route.dossiers.manager.borealis.value.description')}
          </Typography>
        </>
      )}
    </>
  );
};

export default BorealisLeadForm;

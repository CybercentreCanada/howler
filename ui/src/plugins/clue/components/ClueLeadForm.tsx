import { useClueFetcherSelector } from '@cccsaurora/clue-ui/hooks/selectors';
import { Autocomplete, Divider, ListItemText, TextField, Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { LeadFormProps } from 'components/routes/dossiers/LeadEditor';
import uniq from 'lodash-es/uniq';
import { useContext, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const ClueLeadForm: FC<LeadFormProps> = ({ lead, metadata, update, updateMetadata }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const fetchers = useClueFetcherSelector(ctx => ctx.fetchers);

  const [showCustom, setShowCustom] = useState(false);

  return (
    <>
      <Divider orientation="horizontal" />
      <Autocomplete
        disabled={!lead}
        options={Object.keys(fetchers)}
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.clue')} />}
        value={Object.keys(fetchers).includes(lead?.content) ? lead.content : null}
        onChange={(_ev, content) => update({ content, metadata: '{}' })}
        renderOption={({ key, ...props }, option) => (
          <ListItemText
            key={key}
            {...(props as any)}
            sx={{ flexDirection: 'column', alignItems: 'start !important' }}
            primary={<code>{option}</code>}
            secondary={fetchers[option].description}
          />
        )}
      />
      <Autocomplete
        options={
          fetchers[lead?.content]?.supported_types ??
          uniq(Object.values(fetchers).flatMap(fetcher => fetcher.supported_types))
        }
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.clue.type')} />}
        value={metadata?.type ?? null}
        onChange={(_ev, type) => updateMetadata({ type })}
      />
      <Autocomplete
        options={['custom', ...Object.keys(config.indexes.hit)]}
        disabled={!metadata?.type}
        renderInput={params => <TextField {...params} size="small" label={t('route.dossiers.manager.clue.value')} />}
        getOptionLabel={opt => t(opt)}
        value={metadata?.value ?? null}
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
            label={t('route.dossiers.manager.clue.value.custom')}
            value={metadata?.value ?? ''}
            disabled={!metadata?.type}
            fullWidth
            onChange={ev => updateMetadata({ value: ev.target.value })}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: '0 !important' }}>
            {t('route.dossiers.manager.clue.value.description')}
          </Typography>
        </>
      )}
    </>
  );
};

export default ClueLeadForm;

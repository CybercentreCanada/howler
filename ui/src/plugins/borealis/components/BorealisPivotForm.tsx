import { Autocomplete, Divider, Stack, TextField, Typography, useTheme } from '@mui/material';
import { useBorealisActionsSelector } from 'borealis-ui';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { PivotFormProps } from 'components/routes/dossiers/PivotForm';
import { Fragment, useContext, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const BorealisPivotForm: FC<PivotFormProps> = ({ pivot, update }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const actions = useBorealisActionsSelector(ctx => ctx?.availableActions);

  return (
    <>
      <Autocomplete
        fullWidth
        disabled={!pivot}
        options={Object.entries(actions)
          .filter(([_key, definition]) => !!definition && definition.format == 'pivot')
          .map(([key]) => key)}
        renderOption={({ key, ...optionProps }, actionId) => {
          const definition = actions[actionId];

          return (
            <Stack component="li" key={key} {...optionProps} spacing={1}>
              <Stack direction="row" spacing={1} alignSelf="start" alignItems="center">
                <Typography>{definition.name}</Typography>
                <pre
                  style={{
                    fontSize: '0.85rem',
                    border: `thin solid ${theme.palette.divider}`,
                    padding: theme.spacing(0.5),
                    borderRadius: theme.shape.borderRadius
                  }}
                >
                  {actionId}
                </pre>
              </Stack>
              <Typography variant="body2" color="text.secondary" alignSelf="start">
                {definition.summary}
              </Typography>
            </Stack>
          );
        }}
        getOptionLabel={opt => actions[opt]?.name ?? ''}
        renderInput={params => (
          <TextField {...params} size="small" fullWidth label={t('route.dossiers.manager.pivot.value')} />
        )}
        value={pivot?.value ?? ''}
        onChange={(_ev, value) =>
          update({
            value,
            mappings: [
              { key: actions[value].accept_multiple ? 'selectors' : 'selector', field: 'howler.id' },
              ...Object.entries(actions[value].params?.properties ?? [])
                .filter(([property]) => !['selector', 'selectors'].includes(property))
                .map(([prop, schema]) => ({
                  key: prop,
                  field: typeof schema === 'boolean' || !schema.default ? null : 'custom',
                  custom_value: typeof schema !== 'boolean' && !!schema.default ? schema.default.toString() : null
                }))
            ]
          })
        }
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
              options={['custom', 'unset', ...Object.keys(config.indexes.hit)]}
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
    </>
  );
};

export default BorealisPivotForm;

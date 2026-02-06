import { useClueActionsSelector, useClueEnrichSelector } from '@cccsaurora/clue-ui';
import { Icon } from '@iconify/react/dist/iconify.js';
import type { JsonSchema7 } from '@jsonforms/core';
import { Settings } from '@mui/icons-material';
import { Divider, IconButton, Stack, Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import HowlerCard from 'components/elements/display/HowlerCard';
import type { PivotLinkProps } from 'components/elements/hit/related/PivotLink';
import useMySnackbar from 'components/hooks/useMySnackbar';
import get from 'lodash-es/get';
import isBoolean from 'lodash-es/isBoolean';
import isNil from 'lodash-es/isNil';
import type { Mapping } from 'models/entities/generated/Mapping';
import { memo, useCallback, useContext, useState, type FC, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

const CluePivot: FC<PivotLinkProps> = ({ pivot, hit, compact }: PivotLinkProps) => {
  const guessType = useClueEnrichSelector(ctx => ctx?.guessType);

  const { showErrorMessage } = useMySnackbar();
  const { config } = useContext(ApiConfigContext);

  const { i18n, t } = useTranslation();

  const actions = useClueActionsSelector(ctx => ctx?.availableActions ?? {});
  const executeAction = useClueActionsSelector(ctx => ctx?.executeAction);

  const [loading, setLoading] = useState(false);

  const getValue = useCallback(
    (actionId: string, mapping: Mapping) => {
      const parameterSchema = actions[actionId].params?.properties?.[mapping.key];
      if (mapping.field === 'custom') {
        if ((parameterSchema as JsonSchema7)?.type === 'number') {
          return parseFloat(mapping.custom_value);
        }

        if ((parameterSchema as JsonSchema7)?.type === 'integer') {
          return Math.floor(parseFloat(mapping.custom_value));
        }

        return mapping.custom_value;
      }

      if (!Object.keys(config.indexes.hit).includes(mapping.field)) {
        return mapping.field;
      }

      const hitData = get(hit, mapping.field) as string | string[];

      // No schema provided - just pass on the value
      if (!parameterSchema) {
        return hitData;
      }

      // JSON schema is a boolean - we just shove whatever they want in there if it's true, or skip if false
      if (isBoolean(parameterSchema)) {
        return parameterSchema ? hitData : null;
      }

      // It wants a list of values
      if (parameterSchema.type === 'array') {
        // We have a list of values
        if (Array.isArray(hitData)) {
          return hitData;
        } else {
          // We don't have a list of values
          return isNil(hitData) ? [] : [hitData];
        }
      }

      // It wants a single object, but we have a list
      if (Array.isArray(hitData)) {
        // TODO: This is still a little blah.
        return hitData[0];
      }

      // We have a single object and that's what they want
      return hitData;
    },
    [actions, config.indexes.hit, hit]
  );

  const onClueClick = useCallback(
    async (event: MouseEvent<HTMLElement>, forceMenu = false) => {
      event.preventDefault();
      event.stopPropagation();

      if (loading) {
        return;
      }

      if (!actions[pivot.value]) {
        showErrorMessage(t('pivot.clue.missing'));
        return;
      }

      setLoading(true);

      const data: { [index: string]: any } = Object.fromEntries(
        pivot.mappings.map(_mapping => {
          const value = getValue(pivot.value, _mapping);

          if (['selector', 'selectors'].includes(_mapping.key)) {
            if (!value) {
              return _mapping.key === 'selector' ? ['selector', null] : ['selectors', []];
            }

            if (Array.isArray(value)) {
              return [
                _mapping.key,
                value
                  .filter(val => !isNil(val))
                  .map(val => ({
                    type: config.configuration?.mapping?.[_mapping.field] || guessType(val.toString()),
                    value: val
                  }))
              ];
            }

            return [
              _mapping.key,
              {
                type: config.configuration?.mapping?.[_mapping.field] || guessType(value.toString()),
                value
              }
            ];
          }

          return [_mapping.key, value];
        })
      );

      const selectors = (actions[pivot.value].accept_multiple ? [data.selectors] : [data.selector])
        .flat()
        .filter(val => !isNil(val));

      delete data.selector;
      delete data.selectors;

      try {
        await executeAction(pivot.value, selectors, data, { forceMenu });
      } finally {
        setLoading(false);
      }
    },
    [
      actions,
      config.configuration?.mapping,
      executeAction,
      getValue,
      guessType,
      loading,
      pivot.mappings,
      pivot.value,
      showErrorMessage,
      t
    ]
  );

  if (!actions[pivot.value]) {
    return;
  }

  return (
    <HowlerCard
      variant={compact ? 'outlined' : 'elevation'}
      onClick={e => onClueClick(e)}
      sx={[
        theme => ({
          backgroundColor: 'transparent',
          transition: theme.transitions.create(['border-color']),
          '&:hover': { borderColor: 'primary.main' },
          '& > div': {
            height: '100%'
          }
        }),
        loading
          ? { opacity: 0.5, pointerEvents: 'none' }
          : {
              cursor: 'pointer'
            },
        !compact && { border: 'thin solid', borderColor: 'transparent' }
      ]}
    >
      <Stack direction="row" p={compact ? 0.5 : 1} spacing={1} alignItems="center">
        <Icon fontSize="1.5rem" icon={pivot.icon} />
        <Typography>{pivot.label[i18n.language]}</Typography>
        <Divider orientation="vertical" flexItem />
        <IconButton size="small" onClick={e => onClueClick(e, true)}>
          <Settings fontSize="small" />
        </IconButton>
      </Stack>
    </HowlerCard>
  );
};

export default memo(CluePivot);

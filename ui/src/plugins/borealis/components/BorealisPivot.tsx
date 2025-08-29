import { Icon } from '@iconify/react/dist/iconify.js';
import { Settings } from '@mui/icons-material';
import { Divider, IconButton, Stack, Typography } from '@mui/material';
import { useBorealisActionsSelector, useBorealisEnrichSelector } from 'borealis-ui';
import HowlerCard from 'components/elements/display/HowlerCard';
import type { PivotLinkProps } from 'components/elements/hit/related/PivotLink';
import useMySnackbar from 'components/hooks/useMySnackbar';
import { get } from 'lodash-es';
import { memo, useCallback, useState, type FC, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

const BorealisPivot: FC<PivotLinkProps> = ({ pivot, hit, compact }: PivotLinkProps) => {
  const guessType = useBorealisEnrichSelector(ctx => ctx?.guessType);

  const { showErrorMessage } = useMySnackbar();

  const { i18n, t } = useTranslation();

  const actions = useBorealisActionsSelector(ctx => ctx?.availableActions ?? {});
  const executeAction = useBorealisActionsSelector(ctx => ctx?.executeAction);

  const [loading, setLoading] = useState(false);

  const onBorealisClick = useCallback(
    async (event: MouseEvent<HTMLElement>, forceMenu = false) => {
      event.preventDefault();
      event.stopPropagation();

      if (loading) {
        return;
      }

      if (!actions[pivot.value]) {
        showErrorMessage(t('pivot.borealis.missing'));
        return;
      }

      setLoading(true);

      const data: { [index: string]: any } = Object.fromEntries(
        pivot.mappings.map(_mapping => {
          const value = _mapping.field !== 'custom' ? get(hit, _mapping.field) : _mapping.custom_value;

          if (['selector', 'selectors'].includes(_mapping.key)) {
            if (Array.isArray(value)) {
              return [
                _mapping.key,
                value.map(val => ({
                  // TODO: Use the mapped borealis values here eventually
                  type: guessType(val),
                  value: val
                }))
              ];
            }

            return [
              _mapping.key,
              {
                // TODO: Use the mapped borealis values here eventually
                type: guessType(value),
                value
              }
            ];
          }

          return [_mapping.key, value];
        })
      );

      const selectors = (actions[pivot.value].accept_multiple ? [data.selectors] : [data.selector]).flat();

      delete data.selector;
      delete data.selectors;

      try {
        await executeAction(pivot.value, selectors, data, { forceMenu });
      } finally {
        setLoading(false);
      }
    },
    [actions, executeAction, guessType, hit, loading, pivot.mappings, pivot.value, showErrorMessage, t]
  );

  if (!actions[pivot.value]) {
    return;
  }

  return (
    <HowlerCard
      variant={compact ? 'outlined' : 'elevation'}
      onClick={e => onBorealisClick(e)}
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
        <IconButton size="small" onClick={e => onBorealisClick(e, true)}>
          <Settings fontSize="small" />
        </IconButton>
      </Stack>
    </HowlerCard>
  );
};

export default memo(BorealisPivot);

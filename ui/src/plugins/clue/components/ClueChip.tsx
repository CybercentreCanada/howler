import EnrichedChip from '@cccsaurora/clue-ui/components/EnrichedChip';
import { useClueEnrichSelector } from '@cccsaurora/clue-ui/hooks/selectors';
import type EnrichmentProps from '@cccsaurora/clue-ui/types/EnrichmentProps';
import { Chip, type ChipProps } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { PluginChipProps } from 'components/elements/PluginChip';
import { memo, useContext, type FC } from 'react';

const ClueChip: FC<PluginChipProps> = ({ children, value, context, field, hit, ...props }) => {
  const guessType = useClueEnrichSelector(ctx => ctx.guessType);
  const { config } = useContext(ApiConfigContext);

  const type =
    hit?.clue?.types?.find(mapping => mapping.field === field)?.type ||
    config.configuration?.mapping?.[field] ||
    (value ? guessType(value.toString()) : null);

  if (!type) {
    return <Chip {...props}>{children}</Chip>;
  }

  let enrichedProps: EnrichmentProps & ChipProps = {
    ...props,
    value
  };

  if (context === 'summary') {
    enrichedProps = {
      ...enrichedProps,
      sx: [
        ...(Array.isArray(enrichedProps.sx) ? enrichedProps.sx : [enrichedProps.sx]),
        [{ height: '24px', '& .iconify': { fontSize: '1em' } }]
      ]
    };
  } else {
    delete enrichedProps.label;
  }

  return <EnrichedChip {...enrichedProps} type={type} label={props.label} />;
};

export default memo(ClueChip);

import { Chip, type ChipProps } from '@mui/material';
import { EnrichedChip, useBorealisEnrichSelector } from 'borealis-ui';
import type EnrichmentProps from 'borealis-ui/dist/types/EnrichmentProps';
import type { PluginChipProps } from 'components/elements/PluginChip';
import { memo, type FC } from 'react';

const BorealisChip: FC<PluginChipProps> = ({ children, value, context, ...props }) => {
  const guessType = useBorealisEnrichSelector(ctx => ctx.guessType);

  const type = guessType(value);

  if (!type) {
    return <Chip {...props}>{children}</Chip>;
  }

  let enrichedProps: EnrichmentProps & ChipProps = {
    ...props,
    value
  };
  delete enrichedProps.label;

  if (context === 'summary') {
    enrichedProps = {
      ...enrichedProps,
      sx: [
        ...(Array.isArray(enrichedProps.sx) ? enrichedProps.sx : [enrichedProps.sx]),
        [{ height: '24px', '& .iconify': { fontSize: '1em' } }]
      ]
    };
  }

  return <EnrichedChip {...enrichedProps} type={type} />;
};

export default memo(BorealisChip);

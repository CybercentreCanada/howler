import EnrichedChip from '@cccsaurora/clue-ui/components/EnrichedChip';
import type EnrichmentProps from '@cccsaurora/clue-ui/types/EnrichmentProps';
import { Chip, type ChipProps } from '@mui/material';
import type { PluginChipProps } from 'components/elements/PluginChip';
import { memo, type FC } from 'react';
import { useType } from '../utils';

const ClueChip: FC<PluginChipProps> = ({ children, value, context, field, hit, ...props }) => {
  const type = useType(hit, field, value);

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

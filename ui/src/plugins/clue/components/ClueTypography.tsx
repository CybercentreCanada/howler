import type { EnrichedTypographyProps } from '@cccsaurora/clue-ui/components/EnrichedTypography';
import EnrichedTypography from '@cccsaurora/clue-ui/components/EnrichedTypography';
import { useClueEnrichSelector } from '@cccsaurora/clue-ui/hooks/selectors';
import { Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { PluginTypographyProps } from 'components/elements/PluginTypography';
import { memo, useContext, type FC } from 'react';

const ClueTypography: FC<PluginTypographyProps> = ({ children, value, context, field, hit, ...props }) => {
  const guessType = useClueEnrichSelector(ctx => ctx.guessType);
  const { config } = useContext(ApiConfigContext);

  const type =
    hit?.clue?.types?.find(mapping => mapping.field === field)?.type ||
    config.configuration?.mapping?.[field] ||
    (value ? guessType(value.toString()) : null);

  if (!type) {
    return <Typography {...props}>{children ?? value}</Typography>;
  }

  let enrichedProps: EnrichedTypographyProps = {
    ...props,
    value
  };

  if (context === 'banner') {
    enrichedProps = {
      ...enrichedProps,
      slotProps: { stack: { component: 'span' } }
    };
  } else if (context === 'outline') {
    enrichedProps = {
      ...enrichedProps,
      hideLoading: true,
      slotProps: {
        stack: {
          sx: { mr: 'auto' },
          onClick: e => {
            e.preventDefault();
            e.stopPropagation();
          }
        },
        popover: {
          onClick: e => {
            e.preventDefault();
            e.stopPropagation();
          }
        } as any
      }
    };
  } else if (context === 'table') {
    enrichedProps = {
      ...enrichedProps,
      hideLoading: true,
      slotProps: {
        stack: { sx: { width: '100%', '& > p': { textOverflow: 'ellipsis', overflow: 'hidden' } } }
      }
    };
  }

  return <EnrichedTypography {...enrichedProps} type={type} />;
};

export default memo(ClueTypography);

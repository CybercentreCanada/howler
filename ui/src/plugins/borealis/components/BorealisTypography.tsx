import { Typography } from '@mui/material';
import { EnrichedTypography, useBorealisEnrichSelector, type EnrichedTypographyProps } from 'borealis-ui';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { PluginTypographyProps } from 'components/elements/PluginTypography';
import { memo, useContext, type FC } from 'react';

const BorealisTypography: FC<PluginTypographyProps> = ({ children, value, context, ...props }) => {
  const guessType = useBorealisEnrichSelector(ctx => ctx.guessType);

  const { config } = useContext(ApiConfigContext);

  const type = config?.configuration?.mapping?.[value] ?? guessType(value);

  if (!type) {
    return <Typography {...props}>{children}</Typography>;
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

export default memo(BorealisTypography);

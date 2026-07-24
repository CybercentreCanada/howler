import type { ChipOwnProps, ChipProps } from '@mui/material';
import { Chip, Tooltip } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { FC } from 'react';
import React, { memo, useContext, useMemo } from 'react';
import { getParts, normalizedClassification, type FormatProp } from 'utils/classificationParser';

interface EnrichedChipProps {
  classification: string;
  format?: FormatProp;
  isMobile?: boolean;
}

const THEME_TYPES = ['default', 'primary', 'secondary', 'error', 'info', 'success', 'warning'];

const ClassificationChip: FC<EnrichedChipProps & Exclude<ChipProps, 'label'>> = React.memo(
  ({ classification, format = 'short', isMobile = true, ...otherProps }) => {
    const { config } = useContext(ApiConfigContext);

    const parts = useMemo(() => {
      if (!config.c12nDef) {
        return null;
      }

      return getParts(classification, config.c12nDef, format, isMobile);
    }, [classification, config.c12nDef, format, isMobile]);

    const normalized = useMemo(() => {
      if (!config.c12nDef || !parts) {
        return classification;
      }

      return normalizedClassification(parts, config.c12nDef, format, isMobile);
    }, [classification, config.c12nDef, format, isMobile, parts]);

    const chipProps: ChipProps = useMemo(() => {
      const definedColor = parts
        ? config.c12nDef?.levels_styles_map[config.c12nDef?.levels_map[parts.lvlIdx]!]?.color
        : undefined;

      if (THEME_TYPES.includes(definedColor ?? '')) {
        return { color: definedColor as ChipOwnProps['color'] };
      }

      if (definedColor) {
        return { sx: { color: definedColor } };
      }

      return { color: 'default' };
    }, [config.c12nDef?.levels_map, config.c12nDef?.levels_styles_map, parts]);

    return (
      <Tooltip title={classification}>
        <Chip
          variant={otherProps.variant || 'outlined'}
          label={normalized}
          {...chipProps}
          {...otherProps}
          sx={[
            ...(Array.isArray(chipProps.sx) ? chipProps.sx : [chipProps.sx]),
            ...(Array.isArray(otherProps.sx) ? otherProps.sx : [otherProps.sx])
          ]}
        />
      </Tooltip>
    );
  }
);

export default memo(ClassificationChip);

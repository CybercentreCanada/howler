import Box from '@mui/material/Box';
import { alpha, useTheme, type SxProps, type Theme } from '@mui/material/styles';
import type { TsxColoredDotColor, TsxColoredDotProps, TsxColoredDotSize } from './TsxColorDot.types';

const sizeMap: Record<TsxColoredDotSize, number> = {
  small: 10,
  medium: 12,
  large: 14
};

export const TsxColoredDot = ({ color, variant = 'filled', size = 'medium', sx }: TsxColoredDotProps) => {
  const theme = useTheme();

  const colorMap: Record<TsxColoredDotColor, string> = {
    gray: theme.palette.grey[500],
    red: theme.palette.error.light,
    green: theme.palette.success.light,
    yellow: theme.palette.warning.light,
    blue: theme.palette.info.light
  };

  const baseColor = colorMap[color];
  const backgroundColor = variant === 'ghost' ? alpha(baseColor, 0.25) : baseColor;
  const dotSize = sizeMap[size];

  const baseSx: SxProps<Theme> = {
    width: dotSize,
    height: dotSize,
    borderRadius: '50%',
    bgcolor: backgroundColor,
    borderWidth: 2,
    borderStyle: 'solid',
    borderColor: baseColor
  };

  return <Box sx={[baseSx, ...(Array.isArray(sx) ? sx : [sx])]} />;
};

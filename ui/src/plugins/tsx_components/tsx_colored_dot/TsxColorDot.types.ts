import type { SxProps, Theme } from '@mui/material/styles';

export type TsxColoredDotColor = 'gray' | 'red' | 'green' | 'yellow' | 'blue';
export type TsxColoredDotVariant = 'filled' | 'ghost';
export type TsxColoredDotSize = 'small' | 'medium' | 'large';

export type TsxColoredDotProps = {
  color: TsxColoredDotColor;
  variant?: TsxColoredDotVariant;
  size?: TsxColoredDotSize;
  sx?: SxProps<Theme>;
};

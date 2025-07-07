export const MuiButtonColors = ['inherit', 'primary', 'secondary', 'success', 'error', 'info', 'warning'] as const;

export type MuiButtonColorType = (typeof MuiButtonColors)[number];

export const isMuiButtonColor = (color: string): boolean => {
  return MuiButtonColors.some(c => c === color);
};

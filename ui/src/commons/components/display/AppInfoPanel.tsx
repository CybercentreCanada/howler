import { Info } from '@mui/icons-material';
import { Box, Stack, Typography, emphasize, useTheme, type StackProps } from '@mui/material';
import { useTranslation } from 'react-i18next';

export type AppInfoPanelProps = { i18nKey: string } & StackProps;

export default function AppInfoPanel({ i18nKey, ...props }: AppInfoPanelProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const bgColor = emphasize(theme.palette.background.default, 0.1);
  const color = emphasize(bgColor, 0.4);
  return (
    <Stack
      {...props}
      direction="row"
      p={2}
      sx={{
        ...props.sx,
        alignItems: 'center',
        borderRadius: 2,
        backgroundColor: bgColor,
        color: color
      }}
    >
      <Info fontSize="large" />
      <Box m={1} />
      <Typography variant="h5">{t(i18nKey)}</Typography>
    </Stack>
  );
}

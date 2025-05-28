import { Chip, useMediaQuery, useTheme } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const Classification: FC = () => {
  const { config } = useContext(ApiConfigContext);
  const { t } = useTranslation();
  const theme = useTheme();
  const isSm = useMediaQuery(theme.breakpoints.down('md'));

  const label = useMemo(() => {
    if (isSm) {
      return config.c12nDef?.UNRESTRICTED?.replace(/[a-z]/g, '').replace(/ /g, '') ?? '???';
    } else {
      return config.c12nDef?.UNRESTRICTED ?? 'Unknown';
    }
  }, [config.c12nDef?.UNRESTRICTED, isSm]);

  const color = useMemo(
    () => config.c12nDef?.levels_styles_map?.[label.replace(/\/\/.+/, '')]?.color ?? 'default',
    [config.c12nDef?.levels_styles_map, label]
  );

  return <Chip label={t(label)} color={color} sx={{ mr: 1, fontSize: '.9rem', p: 2, textTransform: 'uppercase' }} />;
};

export default Classification;

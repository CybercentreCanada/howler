import { Chip, useMediaQuery, useTheme, type ChipOwnProps } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const Classification: FC = () => {
  const { config, loaded } = useContext(ApiConfigContext);
  const { t } = useTranslation();
  const theme = useTheme();
  const isSm = useMediaQuery(theme.breakpoints.down('md'));

  const c12nDef = loaded ? config.c12nDef : null;

  const label = useMemo(() => {
    if (isSm) {
      return c12nDef?.RESTRICTED?.replace(/[a-z]/g, '').replace(/ /g, '') ?? '???';
    } else {
      return c12nDef?.RESTRICTED ?? 'Unknown';
    }
  }, [c12nDef?.RESTRICTED, isSm]);

  const color = useMemo(
    () => (c12nDef?.levels_styles_map?.[label.replace(/\/\/.+/, '')]?.color ?? 'default') as ChipOwnProps['color'],
    [c12nDef?.levels_styles_map, label]
  );

  return <Chip label={t(label)} color={color} sx={{ mr: 1, fontSize: '.9rem', p: 2, textTransform: 'uppercase' }} />;
};

export default Classification;

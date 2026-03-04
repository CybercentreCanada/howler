import { Stack, Typography, useTheme } from '@mui/material';
import type { TypographyProps } from '@mui/material/Typography';
import PluginTypography from 'components/elements/PluginTypography';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, type FC, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { ensureArray } from 'utils/arrayUtils';
import { HitLayout } from '../HitLayout';

const BannerWrapper: FC<
  PropsWithChildren<
    {
      gridSection?: string;
      i18nKey: string;
      layout: HitLayout;
      value?: string | string[];
      field?: string;
      hit?: Hit;
    } & TypographyProps
  >
> = ({ gridSection, i18nKey, value, field, layout, hit, children, ...typographyProps }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const textVariant = layout === HitLayout.COMFY ? 'body1' : 'caption';
  const compressed = layout === HitLayout.DENSE;

  return (
    <>
      <Typography
        variant={textVariant}
        noWrap={compressed}
        textOverflow={compressed ? 'ellipsis' : 'wrap'}
        fontWeight="bold"
        {...typographyProps}
        sx={[
          { display: 'flex', flexDirection: 'row', borderTop: `thin solid ${theme.palette.divider}` },
          gridSection && { gridArea: `${gridSection}-title` },
          ...(Array.isArray(typographyProps?.sx) ? typographyProps?.sx : [typographyProps?.sx])
        ]}
      >
        {t(i18nKey)}
      </Typography>

      <Stack
        flex={1}
        sx={[
          { borderTop: `thin solid ${theme.palette.divider}`, pr: 1 },
          gridSection && { gridArea: `${gridSection}-content` }
        ]}
      >
        {!!children
          ? children
          : ensureArray(value).map(val => (
              <PluginTypography
                component="span"
                context="banner"
                key={val}
                variant={textVariant}
                noWrap={compressed}
                textOverflow={compressed ? 'ellipsis' : 'wrap'}
                {...typographyProps}
                value={val}
                field={field}
                hit={hit}
              />
            ))}
      </Stack>
    </>
  );
};

export default memo(BannerWrapper);

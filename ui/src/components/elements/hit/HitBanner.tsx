import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  Chip,
  Grid,
  Stack,
  Tooltip,
  Typography,
  chipClasses,
  useTheme,
  type TypographyProps
} from '@mui/material';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { Fragment, useMemo, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { getEscalationColor, getProviderColor } from 'utils/utils';
import PluginTypography from '../PluginTypography';
import AnalyticLink from './elements/AnalyticLink';
import Assigned from './elements/Assigned';
import EscalationChip from './elements/EscalationChip';
import HitTimestamp from './elements/HitTimestamp';
import HitBannerTooltip from './HitBannerTooltip';
import { HitLayout } from './HitLayout';
import RelatedRecords from './related/RelatedRecords';

type HitBannerProps = {
  hit: Hit;
  lazy?: boolean;
  layout?: HitLayout;
  showAssigned?: boolean;
  useListener?: boolean;
};

export interface StatusProps<T extends Hit = Hit> {
  hit: T;
  layout: HitLayout;
}

type HitBannerWrapperProps = {
  compressed: boolean;
  hit: Hit;
  textVariant: TypographyProps['variant'];
  i18nKey: string;
  value: string | string[];
  field: string;
} & TypographyProps;

const Wrapper: FC<HitBannerWrapperProps> = ({
  compressed,
  hit,
  textVariant,
  i18nKey,
  value,
  field,
  ...typographyProps
}) => {
  const { t } = useTranslation();
  const children = (
    <Stack direction="row" spacing={1} flex={1} sx={{ lineHeight: '20px', '& .iconify': { maxHeight: '20px' } }}>
      <Typography
        variant={textVariant}
        noWrap={compressed}
        fontWeight="bold"
        textOverflow={compressed ? 'ellipsis' : 'wrap'}
        {...typographyProps}
        sx={[
          { display: 'flex', flexDirection: 'row' },
          ...(typographyProps?.sx && Array.isArray(typographyProps.sx) ? typographyProps.sx : [typographyProps?.sx])
        ]}
      >
        {t(i18nKey)}:
      </Typography>
      {(Array.isArray(value) ? value : [value]).map(val => (
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
          obj={hit}
        />
      ))}
    </Stack>
  );

  return compressed ? (
    <Tooltip
      title={
        Array.isArray(value) ? (
          <div>
            {value.map(indicator => (
              <p key={indicator} style={{ margin: 0, padding: 0 }}>
                {indicator}
              </p>
            ))}
          </div>
        ) : (
          value
        )
      }
    >
      {children}
    </Tooltip>
  ) : (
    children
  );
};

const HitBanner: FC<HitBannerProps> = ({ hit, lazy = false, layout = HitLayout.NORMAL, showAssigned = true }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const pluginStore = usePluginStore();

  const compressed = useMemo(() => layout === HitLayout.DENSE, [layout]);
  const textVariant = useMemo(() => (layout === HitLayout.COMFY ? 'body1' : 'caption'), [layout]);

  const providerColor = getProviderColor(hit?.event?.provider);

  return (
    <Box sx={{ width: '100%', ml: 0, overflow: 'hidden', color: 'text.primary' }}>
      <Stack spacing={layout !== HitLayout.COMFY ? 0.25 : 1}>
        <Stack direction="row" spacing={0.5} flexWrap="wrap" alignItems="center">
          <HitBannerTooltip hit={hit}>
            <Chip
              sx={{ backgroundColor: providerColor, color: theme.palette.getContrastText(providerColor) }}
              label={hit.organization?.name ?? <Trans i18nKey="unknown" />}
            />
          </HitBannerTooltip>
          <AnalyticLink lazy={lazy} hit={hit} />
          <div style={{ flex: 1 }} />
          <EscalationChip hit={hit} layout={layout} />
          {['in-progress', 'on-hold'].includes(hit.howler.status ?? '') && (
            <Chip sx={{ width: 'fit-content', display: 'inline-flex' }} label={hit.howler.status} color="primary" />
          )}
          <HitTimestamp hit={hit} layout={layout} />
          <Assigned hit={hit} layout={layout} showAssigned={showAssigned} />
          {(hit.howler.related?.length ?? 0) > 0 && <RelatedRecords hit={hit} />}
          {howlerPluginStore.plugins.flatMap(plugin => (
            <Fragment key={plugin}>{pluginStore.executeFunction(`${plugin}.status`, { hit, layout })}</Fragment>
          ))}
        </Stack>
        {hit.howler?.rationale && (
          <Wrapper
            fontWeight="bold"
            color={getEscalationColor(hit.howler.escalation) + '.main'}
            compressed={compressed}
            hit={hit}
            textVariant={textVariant}
            i18nKey="hit.header.rationale"
            value={hit.howler.rationale}
            field="howler.rationale"
          />
        )}
        {hit.howler?.outline && (
          <>
            {hit.howler.outline.threat && (
              <Wrapper
                compressed={compressed}
                hit={hit}
                textVariant={textVariant}
                i18nKey="hit.header.threat"
                value={hit.howler.outline.threat}
                field="howler.outline.threat"
              />
            )}
            {hit.howler.outline.target && (
              <Wrapper
                compressed={compressed}
                hit={hit}
                textVariant={textVariant}
                i18nKey="hit.header.target"
                value={hit.howler.outline.target}
                field="howler.outline.target"
              />
            )}
            {(hit.howler.outline.indicators?.length ?? 0) > 0 && (
              <Stack direction="row" spacing={layout !== HitLayout.COMFY ? 0.25 : 1}>
                <Typography component="span" variant={textVariant} fontWeight="bold" pr={1}>
                  {t('hit.header.indicators')}:
                </Typography>
                <Grid container spacing={0.5}>
                  {uniq(hit.howler.outline.indicators ?? []).map((_indicator, index) => {
                    return (
                      <Grid key={_indicator}>
                        <Stack direction="row">
                          <PluginTypography context="indicators" variant={textVariant} value={_indicator}>
                            {_indicator}
                          </PluginTypography>
                          {index < (hit.howler.outline?.indicators?.length ?? 0) - 1 && (
                            <Typography variant={textVariant}>{','}</Typography>
                          )}
                        </Stack>
                      </Grid>
                    );
                  })}
                </Grid>
              </Stack>
            )}
            {hit.howler.outline.summary && (
              <Wrapper
                compressed={compressed}
                hit={hit}
                textVariant={textVariant}
                i18nKey="hit.header.summary"
                value={hit.howler.outline.summary}
                textOverflow="wrap"
                sx={[compressed && { marginTop: `0 !important` }]}
                field="howler.outline.summary"
              />
            )}

            {hit.howler.links?.[0]?.href && (
              <Chip
                icon={<OpenInNew />}
                label={hit.howler.links[0].title || t('hit.header.link')}
                size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
                component="a"
                href={hit.howler.links[0].href}
                target="_blank"
                rel="noopener noreferrer"
                sx={{ [`.${chipClasses.label}`]: { cursor: 'pointer !important' }, alignSelf: 'start' }}
                onClick={e => {
                  e.stopPropagation();
                }}
              />
            )}
          </>
        )}
      </Stack>
    </Box>
  );
};

export default HitBanner;

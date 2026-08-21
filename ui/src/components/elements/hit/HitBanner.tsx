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
import { Fragment, useCallback, useMemo, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { ESCALATION_COLORS, PROVIDER_COLORS } from 'utils/constants';
import { stringToColor } from 'utils/utils';
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

const HitBanner: FC<HitBannerProps> = ({ hit, lazy = false, layout = HitLayout.NORMAL, showAssigned = true }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const pluginStore = usePluginStore();

  const compressed = useMemo(() => layout === HitLayout.DENSE, [layout]);
  const textVariant = useMemo(() => (layout === HitLayout.COMFY ? 'body1' : 'caption'), [layout]);

  const providerColor = useMemo(() => {
    if (!hit?.event.provider) {
      return PROVIDER_COLORS.unknown;
    }

    return PROVIDER_COLORS[hit?.event.provider] ?? stringToColor(hit?.event.provider);
  }, [hit?.event.provider]);

  /**
   * The tooltips are necessary only when in the most compressed format
   */
  const Wrapper: FC<{ i18nKey: string; value: string | string[]; field: string } & TypographyProps> = useCallback(
    ({ i18nKey, value, field, ...typographyProps }) => {
      const _children = (
        <Stack direction="row" spacing={1} flex={1}>
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
                {value.map(_indicator => (
                  <p key={_indicator} style={{ margin: 0, padding: 0 }}>
                    {_indicator}
                  </p>
                ))}
              </div>
            ) : (
              value
            )
          }
        >
          {_children}
        </Tooltip>
      ) : (
        _children
      );
    },
    [compressed, hit, t, textVariant]
  );

  return (
    <Box sx={{ width: '100%', ml: 0, overflow: 'hidden', color: 'text.primary' }}>
      <Stack spacing={layout !== HitLayout.COMFY ? 0.25 : 1}>
        <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
          <HitBannerTooltip hit={hit}>
            <Chip
              sx={{ backgroundColor: providerColor, color: theme.palette.getContrastText(providerColor) }}
              label={hit.organization?.name ?? <Trans i18nKey="unknown" />}
            />
          </HitBannerTooltip>
          <AnalyticLink lazy={lazy} hit={hit} />
          <div style={{ flex: 1 }} />
          <EscalationChip hit={hit} layout={layout} />
          {['in-progress', 'on-hold'].includes(hit.howler.status) && (
            <Chip sx={{ width: 'fit-content', display: 'inline-flex' }} label={hit.howler.status} color="primary" />
          )}
          <HitTimestamp hit={hit} layout={layout} />
          <Assigned hit={hit} layout={layout} showAssigned={showAssigned} />
          {hit.howler.related?.length > 0 && <RelatedRecords hit={hit} />}
          {howlerPluginStore.plugins.flatMap(plugin => (
            <Fragment key={plugin}>{pluginStore.executeFunction(`${plugin}.status`, { hit, layout })}</Fragment>
          ))}
        </Stack>
        {hit.howler?.rationale && (
          <Typography
            flex={1}
            variant={textVariant}
            color={ESCALATION_COLORS[hit.howler.escalation] + '.main'}
            sx={{ fontWeight: 'bold' }}
          >
            {t('hit.header.rationale')}: {hit.howler.rationale}
          </Typography>
        )}
        {hit.howler?.outline && (
          <>
            <Grid container spacing={layout !== HitLayout.COMFY ? 1 : 2} sx={{ ml: `${theme.spacing(-1)} !important` }}>
              {hit.howler.outline.threat && (
                <Grid>
                  <Wrapper
                    i18nKey="hit.header.threat"
                    value={hit.howler.outline.threat}
                    field="howler.outline.threat"
                  />
                </Grid>
              )}
              {hit.howler.outline.target && (
                <Grid>
                  <Wrapper
                    i18nKey="hit.header.target"
                    value={hit.howler.outline.target}
                    field="howler.outline.target"
                  />
                </Grid>
              )}
            </Grid>
            {hit.howler.outline.indicators?.length > 0 && (
              <Stack direction="row" spacing={layout !== HitLayout.COMFY ? 0.25 : 1}>
                <Typography component="span" variant={textVariant} fontWeight="bold">
                  {t('hit.header.indicators')}:
                </Typography>
                <Grid
                  container
                  spacing={0.5}
                  sx={{ mt: `${theme.spacing(-0.5)} !important`, ml: `${theme.spacing(0.25)} !important` }}
                >
                  {uniq(hit.howler.outline.indicators).map((_indicator, index) => {
                    return (
                      <Grid key={_indicator}>
                        <Stack direction="row">
                          <PluginTypography context="indicators" variant={textVariant} value={_indicator}>
                            {_indicator}
                          </PluginTypography>
                          {index < hit.howler.outline.indicators.length - 1 && (
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
                i18nKey="hit.header.summary"
                value={hit.howler.outline.summary}
                paragraph
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

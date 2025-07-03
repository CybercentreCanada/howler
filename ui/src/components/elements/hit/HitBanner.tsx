import {
  Box,
  Chip,
  Divider,
  Grid,
  Stack,
  Tooltip,
  Typography,
  avatarClasses,
  iconButtonClasses,
  useTheme,
  type TypographyProps
} from '@mui/material';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { useCallback, useContext, useEffect, useMemo, useState, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';
import { ESCALATION_COLORS, PROVIDER_COLORS } from 'utils/constants';
import { stringToColor } from 'utils/utils';
import PluginTypography from '../PluginTypography';
import Assigned from './elements/Assigned';
import EscalationChip from './elements/EscalationChip';
import HitTimestamp from './elements/HitTimestamp';
import HitBannerTooltip from './HitBannerTooltip';
import { HitLayout } from './HitLayout';

type HitBannerProps = {
  hit: Hit;
  layout?: HitLayout;
  showAssigned?: boolean;
  useListener?: boolean;
};

export interface StatusProps<T extends Hit = Hit> {
  hit: T;
  layout: HitLayout;
}

const HitBanner: FC<HitBannerProps> = ({ hit, layout = HitLayout.NORMAL, showAssigned = true }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { getIdFromName } = useContext(AnalyticContext);
  const theme = useTheme();
  const pluginStore = usePluginStore();

  const [analyticId, setAnalyticId] = useState<string>();

  const compressed = useMemo(() => layout === HitLayout.DENSE, [layout]);
  const textVariant = useMemo(() => (layout === HitLayout.COMFY ? 'body1' : 'caption'), [layout]);

  useEffect(() => {
    getIdFromName(hit?.howler.analytic).then(setAnalyticId);
  }, [getIdFromName, hit]);

  const providerColor = useMemo(
    () => PROVIDER_COLORS[hit.event?.provider ?? 'unknown'] ?? stringToColor(hit.event.provider),
    [hit.event?.provider]
  );

  const mitreId = useMemo(() => {
    if (hit.threat?.framework?.toLowerCase().startsWith('mitre')) {
      return;
    }

    let _id = hit.threat?.tactic?.id;
    if (_id && config.lookups.icons.includes(_id)) {
      return _id;
    }

    _id = hit.threat?.technique?.id;
    if (_id && config.lookups.icons.includes(_id)) {
      return _id;
    }
  }, [config.lookups.icons, hit.threat?.framework, hit.threat?.tactic?.id, hit.threat?.technique?.id]);

  const iconUrl = useMemo(() => {
    if (!mitreId) {
      return;
    }

    return `/api/static/mitre/${mitreId}.svg`;
  }, [mitreId]);

  const leftBox = useMemo(() => {
    if (hit.howler.is_bundle) {
      return (
        <Box
          sx={{
            alignSelf: 'stretch',
            backgroundColor: providerColor,
            borderRadius: theme.shape.borderRadius,
            minWidth: '15px'
          }}
        />
      );
    } else {
      return (
        <HitBannerTooltip hit={hit}>
          <Box
            sx={{
              gridColumn: { xs: 'span 3', sm: 'span 1' },
              minWidth: '90px',
              backgroundColor: providerColor,
              color: theme.palette.getContrastText(providerColor),
              alignSelf: 'start',
              borderRadius: theme.shape.borderRadius,
              p: compressed ? 0.5 : 1,
              pt: 2,
              pl: 1
            }}
            display="flex"
            flexDirection="column"
          >
            <Typography variant={compressed ? 'caption' : 'body1'} style={{ wordBreak: 'break-all' }}>
              {hit.organization?.name ?? <Trans i18nKey="unknown" />}
            </Typography>
            {iconUrl && (
              <Box
                sx={{
                  width: '40px',
                  height: '40px',
                  mask: `url("${iconUrl}")`,
                  maskSize: 'cover',
                  background: theme.palette.getContrastText(providerColor)
                }}
              />
            )}
          </Box>
        </HitBannerTooltip>
      );
    }
  }, [compressed, hit, iconUrl, providerColor, theme.palette, theme.shape.borderRadius]);

  /**
   * The tooltips are necessary only when in the most compressed format
   */
  const Wrapper: FC<{ i18nKey: string; value: string | string[] } & TypographyProps> = useCallback(
    ({ i18nKey, value, ...typographyProps }) => {
      const _children = (
        <Stack direction="row" spacing={1} flex={1}>
          <Typography
            variant={textVariant}
            noWrap={compressed}
            textOverflow={compressed ? 'ellipsis' : 'wrap'}
            {...typographyProps}
            sx={[
              { display: 'flex', flexDirection: 'row' },
              ...(Array.isArray(typographyProps?.sx) ? typographyProps?.sx : [typographyProps?.sx])
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
    [compressed, t, textVariant]
  );

  return (
    <Box
      display="grid"
      gridTemplateColumns="minmax(0, auto) minmax(0, 1fr) minmax(0, auto)"
      alignItems="stretch"
      sx={{ width: '100%', ml: 0, overflow: 'hidden' }}
    >
      {leftBox}
      <Stack
        sx={{
          height: '100%',
          padding: theme.spacing(1),
          gridColumn: { xs: 'span 3', sm: 'span 1', md: 'span 1' }
        }}
        spacing={layout !== HitLayout.COMFY ? 1 : 2}
        divider={
          <Divider
            orientation="horizontal"
            sx={[
              layout !== HitLayout.COMFY && { marginTop: '4px !important' },
              { mr: `${theme.spacing(-1)} !important` }
            ]}
          />
        }
      >
        <Typography
          variant={compressed ? 'body1' : 'h6'}
          fontWeight={compressed && 'bold'}
          sx={{ alignSelf: 'start', '& a': { color: 'text.primary' } }}
        >
          {analyticId ? (
            <Link to={`/analytics/${analyticId}`} onClick={e => e.stopPropagation()}>
              {hit.howler.analytic}
            </Link>
          ) : (
            hit.howler.analytic
          )}
          {hit.howler.detection && ': '}
          {hit.howler.detection}
        </Typography>
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
                <Grid item>
                  <Wrapper i18nKey="hit.header.threat" value={hit.howler.outline.threat} />
                </Grid>
              )}
              {hit.howler.outline.target && (
                <Grid item>
                  <Wrapper i18nKey="hit.header.target" value={hit.howler.outline.target} />
                </Grid>
              )}
            </Grid>
            {hit.howler.outline.indicators?.length > 0 && (
              <Stack direction="row" spacing={1}>
                <Typography component="span" variant={textVariant}>
                  {t('hit.header.indicators')}:
                </Typography>
                <Grid
                  container
                  spacing={0.5}
                  sx={{ mt: `${theme.spacing(-0.5)} !important`, ml: `${theme.spacing(0.25)} !important` }}
                >
                  {uniq(hit.howler.outline.indicators).map((_indicator, index) => {
                    return (
                      <Grid key={_indicator} item>
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
              />
            )}
          </>
        )}
      </Stack>
      <Stack
        direction="column"
        spacing={layout !== HitLayout.COMFY ? 0.5 : 1}
        alignSelf="stretch"
        sx={[
          { minWidth: 0, alignItems: { sm: 'end', md: 'start' }, flex: 1, pl: 1 },
          compressed && {
            [`& .${avatarClasses.root}`]: {
              height: theme.spacing(3),
              width: theme.spacing(3)
            },
            [`& .${iconButtonClasses.root}`]: {
              height: theme.spacing(3),
              width: theme.spacing(3)
            }
          }
        ]}
      >
        <HitTimestamp hit={hit} layout={layout} />
        {showAssigned && <Assigned hit={hit} layout={layout} />}
        <Stack direction="row" spacing={layout !== HitLayout.COMFY ? 0.5 : 1}>
          <EscalationChip hit={hit} layout={layout} />
          {['in-progress', 'on-hold'].includes(hit.howler.status) && (
            <Chip
              sx={{ width: 'fit-content', display: 'inline-flex' }}
              label={hit.howler.status}
              size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
              color="primary"
            />
          )}
          {hit.howler.is_bundle && (
            <Chip
              size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
              label={t('hit.header.bundlesize', { hits: hit.howler.hits.length })}
            />
          )}
        </Stack>
        {howlerPluginStore.plugins.flatMap(plugin => pluginStore.executeFunction(`${plugin}.status`, { hit, layout }))}
      </Stack>
    </Box>
  );
};

export default HitBanner;

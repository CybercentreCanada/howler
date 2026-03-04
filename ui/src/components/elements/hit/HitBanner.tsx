import { Box, Chip, Stack, Typography, avatarClasses, iconButtonClasses, useTheme } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { Hit } from 'models/entities/generated/Hit';
import howlerPluginStore from 'plugins/store';
import { useContext, useEffect, useMemo, useState, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';
import { ESCALATION_COLORS, PROVIDER_COLORS } from 'utils/constants';
import { stringToColor } from 'utils/utils';
import OutlineGrid from './banner/OutlineGrid';
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
  const theme = useTheme();
  const pluginStore = usePluginStore();
  const { getMatchingAnalytic } = useMatchers();

  const [analyticId, setAnalyticId] = useState<string>();

  const textVariant = layout === HitLayout.COMFY ? 'body1' : 'caption';
  const compressed = layout === HitLayout.DENSE;

  useEffect(() => {
    if (!hit?.howler.analytic) {
      return;
    }

    getMatchingAnalytic(hit).then(analytic => setAnalyticId(analytic?.analytic_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit?.howler.analytic]);

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

  return (
    <Box
      display="grid"
      gridTemplateColumns="auto 1fr auto"
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
        spacing={layout !== HitLayout.COMFY ? 0.5 : 1}
      >
        <Typography
          variant={compressed ? 'body1' : 'h6'}
          fontWeight={compressed && 'bold'}
          sx={{ alignSelf: 'start', '& a': { color: 'text.primary' } }}
        >
          {analyticId ? (
            <Link
              to={`/analytics/${analyticId}`}
              onAuxClick={e => {
                e.stopPropagation();
              }}
              onClick={e => {
                e.stopPropagation();
              }}
            >
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
        <OutlineGrid hit={hit} layout={layout} />
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

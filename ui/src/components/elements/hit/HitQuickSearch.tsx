import { Box, Chip, Divider, Stack, Tooltip, Typography, useMediaQuery, useTheme } from '@mui/material';
import type { AppSearchItemRendererOption } from 'commons/components/app/AppSearchService';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { memo, useMemo } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { ESCALATION_COLORS, PROVIDER_COLORS, STATUS_COLORS } from 'utils/constants';
import { formatDate, stringToColor } from 'utils/utils';

type QuickSearchProps = {
  hit: Hit;
  options: AppSearchItemRendererOption<Hit>;
};

const HitQuickSearch: FC<QuickSearchProps> = ({ hit, options }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isUnderLg = useMediaQuery(theme.breakpoints.down('lg'));

  const providerColor = useMemo(
    () => PROVIDER_COLORS[hit.event?.provider ?? 'unknown'] ?? stringToColor(hit.event.provider),
    [hit.event?.provider]
  );

  return (
    <Box
      sx={{ overflow: 'hidden', borderBottom: `thin solid ${theme.palette.divider}`, pb: 1, mb: 0 }}
      display="grid"
      gridTemplateColumns="minmax(0, 1fr) minmax(0, auto)"
    >
      <Stack flexGrow={1} gridColumn={options.state.mode === 'inline' ? 'span 2' : ''}>
        <Typography variant="body1" fontWeight="bold">
          {hit.howler.analytic}
          {hit.howler.detection && ': '}
          {hit.howler.detection}
        </Typography>
        {options.state.mode !== 'inline' && hit.howler?.outline && (
          <Tooltip
            placement={isUnderLg ? 'bottom' : 'left'}
            componentsProps={{
              tooltip: {
                sx: {
                  fontSize: 12,
                  backgroundColor: theme.palette.background.paper,
                  color: theme.palette.getContrastText(theme.palette.background.paper)
                }
              }
            }}
            title={
              <Stack divider={<Divider sx={{ my: 0.5 }} />}>
                <div>
                  <Trans i18nKey="hit.header.threat" />: {hit.howler.outline.threat}
                </div>
                <div>
                  <Trans i18nKey="hit.header.target" />: {hit.howler.outline.target}
                </div>
                <div>{hit.howler.outline.indicators.join(', ')}</div>
              </Stack>
            }
          >
            <Stack direction={{ xs: 'column', sm: 'column' }} flex={1}>
              <Typography variant="caption" textOverflow="ellipsis" sx={{ wordBreak: 'break-all', overflow: 'hidden' }}>
                <Trans i18nKey="hit.header.threat" />: {hit.howler.outline.threat}
              </Typography>
              <Typography variant="caption" textOverflow="ellipsis" sx={{ wordBreak: 'break-all', overflow: 'hidden' }}>
                <Trans i18nKey="hit.header.target" />: {hit.howler.outline.target}
              </Typography>
              <Typography variant="caption" textOverflow="ellipsis" sx={{ wordBreak: 'break-all', overflow: 'hidden' }}>
                <Trans i18nKey="hit.header.indicators" />: {hit.howler.outline.indicators.map(i => i).join(', ')}
              </Typography>
            </Stack>
          </Tooltip>
        )}
      </Stack>

      <Stack alignItems={options.state.mode === 'fullscreen' ? 'end' : 'start'} spacing={0.5}>
        {options.state.mode === 'fullscreen' && <Chip label={formatDate(hit.timestamp)} size="small" />}
        <Stack direction="row" spacing={0.5}>
          {options.state.mode === 'inline' && <Chip label={formatDate(hit.timestamp)} size="small" />}
          <Chip
            sx={{
              backgroundColor: providerColor,
              color: theme.palette.getContrastText(providerColor)
            }}
            label={hit.organization?.name ?? <Trans i18nKey="unknown" />}
            size="small"
          />
          <Chip label={hit.howler.escalation} size="small" color={ESCALATION_COLORS[hit.howler.escalation]} />
        </Stack>
        <Stack direction="row" spacing={0.5}>
          <Chip
            sx={{
              '& .MuiChip-icon': {
                marginLeft: 0
              }
            }}
            label={
              hit?.howler.assignment !== 'unassigned'
                ? hit?.howler.assignment
                : t('app.drawer.hit.assignment.unassigned.name')
            }
            size="small"
          />
          <Chip label={hit.howler.status} size="small" color={STATUS_COLORS[hit.howler.status]} />
        </Stack>
      </Stack>
    </Box>
  );
};

export default memo(HitQuickSearch);

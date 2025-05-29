import { Lock } from '@mui/icons-material';
import { Chip, Grid, Stack, Tooltip, Typography } from '@mui/material';
import { get } from 'lodash-es';
import type { Antivirus } from 'models/entities/generated/Antivirus';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';

const TAGS = [
  'assemblyline.antivirus',
  'assemblyline.behaviour',
  'assemblyline.heuristic',
  'assemblyline.yara',
  'assemblyline.attribution',
  'assemblyline.mitre.tactic',
  'assemblyline.mitre.technique'
];

const VERDICT_COLORS: {
  [verdict: string]: 'error' | 'warning' | 'info' | 'primary' | 'default' | 'secondary' | 'success';
} = {
  malicious: 'error',
  suspicious: 'warning',
  info: 'info',
  safe: 'primary'
};

const VERDICT_ORDER = ['malicious', 'suspicious', 'safe', 'info'];

const ARRAY_LIMIT = 10;

const sortByVerdict = (a: Antivirus, b: Antivirus): -1 | 0 | 1 => {
  return VERDICT_ORDER.indexOf(a.verdict) > VERDICT_ORDER.indexOf(b.verdict)
    ? 1
    : VERDICT_ORDER.indexOf(b.verdict) > VERDICT_ORDER.indexOf(a.verdict)
      ? -1
      : 0;
};

const AssemblyLineRules: FC<{ hit: Hit }> = ({ hit }) => {
  const { t } = useTranslation();

  const ipArr: string[] = (hit.related.ip ?? []).filter(e => !!e).slice(0, ARRAY_LIMIT);

  const tagsArr = TAGS.map(each => get(hit, each) as Antivirus)
    .filter(tag => !!tag?.value)
    .sort(sortByVerdict)
    .slice(0, ARRAY_LIMIT);

  return (
    <Grid container direction="row" justifyContent="center" sx={{ position: 'relative' }}>
      <Tooltip title={t('route.templates.builtin')}>
        <Lock fontSize="small" sx={{ position: 'absolute', right: 0, top: 0 }} />
      </Tooltip>
      <Grid item xs={2}>
        <Typography variant="caption" fontWeight="bold">
          {t('outline.assemblyline.file_path')}:
        </Typography>
      </Grid>
      <Grid item xs={10}>
        <Typography variant="caption">{hit.file.path ?? t('unknown')}</Typography>
      </Grid>
      <Grid item xs={2}>
        <Typography variant="caption" fontWeight="bold">
          {t('outline.assemblyline.last_modified')}:
        </Typography>
      </Grid>
      <Grid item xs={10}>
        <Typography variant="caption">
          {hit.cbs?.sharepoint?.modified?.user ?? t('unknown')} {t('using')}{' '}
          {hit.cbs?.sharepoint?.modified?.application ?? t('unknown')} {t('on')} {hit.file?.mtime ?? t('unknown')}
        </Typography>
      </Grid>
      <Grid item xs={2}>
        <Typography variant="caption" fontWeight="bold">
          {t('outline.assemblyline.beacons')}:
        </Typography>
      </Grid>
      <Grid item xs={10}>
        <Stack direction="row" spacing={0.5} sx={{ mb: 0.5 }}>
          {ipArr.map(analytic => {
            return (
              <Grid item key={analytic}>
                <Chip label={analytic} variant="outlined" size="small" />
              </Grid>
            );
          })}
          {ipArr.length < 1 && (
            <Grid item>
              <Chip label={t('none')} variant="outlined" size="small" />
            </Grid>
          )}
        </Stack>
      </Grid>
      <Grid item xs={2}>
        <Typography variant="caption" fontWeight="bold">
          {t('outline.assemblyline.tags')}:
        </Typography>
      </Grid>
      <Grid item xs={10}>
        <Stack direction="row" spacing={0.5} sx={{ mb: 0.5 }}>
          {tagsArr.map(analytic => {
            return (
              <Grid item key={analytic?.value + analytic?.verdict + analytic?.type + analytic?.subtype}>
                <Chip
                  label={analytic?.value}
                  color={
                    analytic?.verdict in VERDICT_COLORS
                      ? VERDICT_COLORS[analytic?.verdict as 'malicious' | 'suspicious' | 'safe' | 'info']
                      : 'error'
                  }
                  variant="outlined"
                  size="small"
                />
              </Grid>
            );
          })}
          {tagsArr.length < 1 && (
            <Grid item>
              <Chip label={t('none')} variant="outlined" size="small" />
            </Grid>
          )}
        </Stack>
      </Grid>
    </Grid>
  );
};

export default memo(AssemblyLineRules);

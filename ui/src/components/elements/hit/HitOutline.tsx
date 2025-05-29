import { Box, Divider, Skeleton, Typography } from '@mui/material';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { createElement, memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { HitLayout } from './HitLayout';
import DefaultOutline from './outlines/DefaultOutline';

export const DEFAULT_FIELDS = ['howler.hash'];

const HitOutline: FC<{ hit: Hit; layout: HitLayout; type?: 'global' | 'personal' }> = ({ hit, layout, type }) => {
  const { t } = useTranslation();

  const loaded = useContextSelector(TemplateContext, ctx => ctx.loaded);
  const getMatchingTemplate = useContextSelector(TemplateContext, ctx => ctx.getMatchingTemplate);

  const template = useMemo(() => getMatchingTemplate(hit), [getMatchingTemplate, hit]);

  const outline = useMemo(() => {
    if (template && template.type === type) {
      return createElement(DefaultOutline, {
        hit,
        layout,
        template,
        fields: template.keys
      });
    } else if (!loaded) {
      return <Skeleton variant="rounded" height="50px" />;
    } else if (template) {
      return createElement(DefaultOutline, {
        hit,
        layout,
        template,
        fields: template.keys,
        readonly: template.type === 'readonly'
      });
    } else {
      return createElement(DefaultOutline, {
        hit,
        layout,
        fields: DEFAULT_FIELDS
      });
    }
  }, [hit, layout, loaded, template, type]);

  return (
    <Box sx={{ py: 1, width: '100%', pr: 2 }}>
      {layout === HitLayout.COMFY && (
        <Typography variant="body1" fontWeight="bold" sx={{ mb: 1 }}>
          {t('hit.details.title')}
        </Typography>
      )}
      {layout !== HitLayout.DENSE && <Divider orientation="horizontal" sx={{ mb: 1 }} />}
      {outline}
    </Box>
  );
};

export default memo(HitOutline);

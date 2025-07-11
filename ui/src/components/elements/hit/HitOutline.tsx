import { Box, Divider, Typography } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { WithMetadata } from 'models/WithMetadata';
import type { FC } from 'react';
import { createElement, memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { HitLayout } from './HitLayout';
import DefaultOutline from './outlines/DefaultOutline';

export const DEFAULT_FIELDS = ['howler.hash'];

const HitOutline: FC<{ hit: WithMetadata<Hit>; layout: HitLayout }> = ({ hit, layout }) => {
  const { t } = useTranslation();

  const { getMatchingTemplate } = useMatchers();

  const [template, setTemplate] = useState<Template>(null);

  useEffect(() => {
    getMatchingTemplate(hit).then(setTemplate);
  }, [getMatchingTemplate, hit]);

  const outline = useMemo(() => {
    if (template) {
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
  }, [hit, layout, template]);

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

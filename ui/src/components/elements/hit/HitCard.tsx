import { CardContent, Skeleton } from '@mui/material';
import { HitContext } from 'components/app/providers/HitProvider';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import type { FC } from 'react';
import { memo, useEffect } from 'react';
import { useContextSelector } from 'use-context-selector';
import HowlerCard from '../display/HowlerCard';
import HitBanner from './HitBanner';
import HitLabels from './HitLabels';
import { HitLayout } from './HitLayout';
import HitOutline from './HitOutline';

const HitCard: FC<{ id?: string; layout: HitLayout; readOnly?: boolean }> = ({ id, layout, readOnly = true }) => {
  const refresh = useContextSelector(TemplateContext, ctx => ctx.refresh);

  const getHit = useContextSelector(HitContext, ctx => ctx.getHit);
  const hit = useContextSelector(HitContext, ctx => ctx.hits[id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!hit) {
      getHit(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!hit) {
    return <Skeleton variant="rounded" height="200px" />;
  }

  return (
    <HowlerCard tabIndex={0} sx={{ position: 'relative' }}>
      <CardContent>
        <HitBanner hit={hit} layout={layout} />
        {layout !== HitLayout.DENSE && (
          <>
            <HitOutline hit={hit} layout={layout} />
            <HitLabels hit={hit} readOnly={readOnly} />
          </>
        )}
      </CardContent>
    </HowlerCard>
  );
};

export default memo(HitCard);

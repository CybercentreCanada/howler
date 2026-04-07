import { CardContent, Skeleton } from '@mui/material';
import { RecordContext } from 'components/app/providers/RecordProvider';
import type { FC } from 'react';
import { memo, useEffect } from 'react';
import { useContextSelector } from 'use-context-selector';
import HowlerCard from '../display/HowlerCard';
import HitBanner from './HitBanner';
import HitLabels from './HitLabels';
import type { HitLayout } from './HitLayout';
import HitOutline from './HitOutline';

const HitCard: FC<{
  id?: string;
  lazy?: boolean;
  layout: HitLayout;
  readOnly?: boolean;
  elevation?: number;
}> = ({ id, layout, readOnly = true, lazy = false, elevation }) => {
  const getRecord = useContextSelector(RecordContext, ctx => ctx.getRecord);
  const hit = useContextSelector(RecordContext, ctx => ctx.records[id] as Hit);

  useEffect(() => {
    if (!hit && !lazy) {
      getRecord(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!hit) {
    return <Skeleton variant="rounded" height="200px" />;
  }

  return (
    <HowlerCard id={hit?.howler.id} tabIndex={0} sx={{ position: 'relative' }} elevation={elevation}>
      <CardContent>
        <HitBanner hit={hit} layout={layout} lazy={lazy} />
        <HitOutline hit={hit} layout={layout} lazy={lazy} />
        <HitLabels hit={hit} readOnly={readOnly} />
      </CardContent>
    </HowlerCard>
  );
};

export default memo(HitCard);

import { CardContent, Skeleton } from '@mui/material';
import { hit } from 'api/search';
import { RecordContext } from 'components/app/providers/RecordProvider';
import HowlerCard from 'components/elements/display/HowlerCard';
import type { Observable } from 'models/entities/generated/Observable';
import { memo, useEffect, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import ObservablePreview from './ObservablePreview';

const ObservableCard: FC<{ id?: string; observable?: Observable }> = ({ id, observable: _observable }) => {
  const getRecord = useContextSelector(RecordContext, ctx => ctx.getRecord);
  const observable = useContextSelector(RecordContext, ctx => _observable ?? (ctx.records[id] as Observable));

  useEffect(() => {
    if (!observable) {
      getRecord(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!hit) {
    return <Skeleton variant="rounded" height="200px" />;
  }

  return (
    <HowlerCard sx={{ position: 'relative' }}>
      <CardContent>
        <ObservablePreview observable={observable} />
      </CardContent>
    </HowlerCard>
  );
};

export default memo(ObservableCard);

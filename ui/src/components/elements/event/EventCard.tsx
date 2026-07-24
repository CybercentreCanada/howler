import { CardContent, Skeleton } from '@mui/material';
import { RecordContext } from 'components/app/providers/RecordProvider';
import HowlerCard from 'components/elements/display/HowlerCard';
import type { Event } from 'models/entities/generated/Event';
import { memo, useEffect, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import EventPreview from './EventPreview';

const EventCard: FC<{ id?: string; event?: Event }> = ({ id, event: _event }) => {
  const getRecord = useContextSelector(RecordContext, ctx => ctx.getRecord);
  const event = useContextSelector(RecordContext, ctx => _event ?? (ctx.records[id!] as Event));

  useEffect(() => {
    if (!event) {
      void getRecord(id!);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!event) {
    return <Skeleton variant="rounded" height="200px" />;
  }

  return (
    <HowlerCard sx={{ position: 'relative' }}>
      <CardContent>
        <EventPreview event={event} />
      </CardContent>
    </HowlerCard>
  );
};

export default memo(EventCard);

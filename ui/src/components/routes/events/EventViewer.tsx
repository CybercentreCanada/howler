import { Box, Skeleton } from '@mui/material';
import api from 'api';
import ObjectDetails from 'components/elements/ObjectDetails';
import useMyApi from 'components/hooks/useMyApi';
import type { Event } from 'models/entities/generated/Event';
import { useEffect, useState, type FC } from 'react';

const EventViewer: FC<{ event?: Event; eventId?: string }> = ({ event: provided, eventId }) => {
  const { dispatchApi } = useMyApi();

  const [event, setEvent] = useState<Event | null>(null);

  useEffect(() => {
    if (provided) {
      setEvent(provided);
    }
  }, [provided]);

  useEffect(() => {
    if (eventId) {
      void dispatchApi(api.v2.search.post<Event>('event', { query: `howler.id:${eventId}`, rows: 1 }), {
        throwError: false
      }).then(res => setEvent(res?.items[0] ?? null));
    }
  }, [dispatchApi, eventId]);

  return <Box p={1}>{event ? <ObjectDetails obj={event} /> : <Skeleton height={120} />}</Box>;
};

export default EventViewer;

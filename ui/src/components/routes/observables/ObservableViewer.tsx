import { Box, Skeleton } from '@mui/material';
import api from 'api';
import ObjectDetails from 'components/elements/ObjectDetails';
import useMyApi from 'components/hooks/useMyApi';
import type { Observable } from 'models/entities/generated/Observable';
import { useEffect, useState, type FC } from 'react';

const ObservableViewer: FC<{ observable?: Observable; observableId?: string }> = ({
  observable: provided,
  observableId
}) => {
  const { dispatchApi } = useMyApi();

  const [observable, setObservable] = useState<Observable>(null);

  useEffect(() => {
    if (provided) {
      setObservable(provided);
    }
  }, [provided]);

  useEffect(() => {
    if (observableId) {
      dispatchApi(api.v2.search.post<Observable>('observable', { query: `howler.id:${observableId}`, rows: 1 }), {
        throwError: false
      }).then(res => setObservable(res.items[0]));
    }
  }, [dispatchApi, observableId]);

  if (!observable) {
    return;
  }

  return <Box p={1}>{observable ? <ObjectDetails obj={observable} /> : <Skeleton height={120} />}</Box>;
};

export default ObservableViewer;

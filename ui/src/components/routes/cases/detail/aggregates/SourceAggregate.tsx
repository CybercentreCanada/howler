import { Chip, Grid, Skeleton } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useMemo, useState, type FC } from 'react';
import useCase from '../../hooks/useCase';

const SourceAggregate: FC<{ case: Case }> = ({ case: providedCase }) => {
  const { dispatchApi } = useMyApi();
  const { case: _case } = useCase({ case: providedCase });

  const [analytics, setAnalytics] = useState([]);

  const hitIds = useMemo(
    () =>
      _case?.items
        .filter(item => item.type === 'hit')
        .map(item => item.value)
        .filter(value => !!value),
    [_case?.items]
  );

  useEffect(() => {
    dispatchApi(api.v2.search.post('hit', { query: `howler.id:(${hitIds.join(' OR ')})`, fl: 'howler.analytic' }))
      .then(response => response?.items.map(hit => hit.howler.analytic) ?? [])
      .then(_analytics => setAnalytics(uniq(_analytics)));

    api.v2.search.facet.post(['hit', 'observable'], {
      query: `howler.id:(${hitIds.join(' OR ')})`,
      fields: ['howler.analytic']
    });
  }, [dispatchApi, hitIds]);

  if (!_case) {
    return <Skeleton height={12} variant="rounded" />;
  }

  return (
    <Grid container spacing={1}>
      {analytics.map(_analytic => (
        <Grid key={_analytic} item>
          <Chip size="small" label={_analytic} />
        </Grid>
      ))}
    </Grid>
  );
};

export default SourceAggregate;

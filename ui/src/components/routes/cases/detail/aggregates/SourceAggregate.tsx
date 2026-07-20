import { Chip, Grid, Skeleton } from '@mui/material';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import { useMemo, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import useCase from '../../hooks/useCase';

const SourceAggregate: FC<{ case: Case }> = ({ case: providedCase }) => {
  const { case: _case } = useCase({ case: providedCase });

  const records = useContextSelector(RecordContext, ctx => ctx.records);

  const analytics = useMemo(() => {
    if (!_case) {
      return [];
    }

    const hitIds = _case.items
      .filter(item => item.type === 'hit')
      .map(item => item.value)
      .filter(value => !!value);

    return uniq(hitIds.map(id => (records[id] as Hit | undefined)?.howler?.analytic).filter(analytic => !!analytic));
  }, [_case, records]);

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

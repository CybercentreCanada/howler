import { Add } from '@mui/icons-material';
import { Box, Chip, chipClasses, Grid, type SxProps } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import { memo, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import HitFilter from './shared/HitFilter';
import HitSort from './shared/HitSort';
import SearchSpan from './shared/SearchSpan';
import ViewLink from './ViewLink';

const QuerySettings: FC<{ verticalSorters?: boolean; boxSx?: SxProps }> = ({ boxSx }) => {
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const selectedView = useContextSelector(ViewContext, ctx => ctx.views[viewId]);
  const filters = useContextSelector(ParameterContext, ctx => ctx.filters);
  const addFilter = useContextSelector(ParameterContext, ctx => ctx.addFilter);

  return (
    <Box sx={boxSx ?? { position: 'relative', maxWidth: '1200px' }}>
      <Grid
        container
        spacing={1}
        sx={[
          viewId &&
            !selectedView && {
              opacity: 0.25,
              pointerEvents: 'none'
            }
        ]}
      >
        <Grid item>
          <HitSort />
        </Grid>
        <Grid item>
          <SearchSpan />
        </Grid>
        <Grid item>
          <ViewLink />
        </Grid>
        {filters.map((filter, id) => (
          <Grid item>
            <HitFilter id={id} value={filter} />
          </Grid>
        ))}
        <Grid item>
          <Chip
            variant="outlined"
            deleteIcon={<Add fontSize="small" />}
            onDelete={() => addFilter('howler.id:*')}
            sx={{ [`& > .${chipClasses.label}`]: { paddingRight: 0 } }}
            size="small"
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default memo(QuerySettings);

import { Box, Stack, type SxProps } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import { memo, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import HitFilter from './HitFilter';
import HitSort from './HitSort';
import SearchSpan from './SearchSpan';

const QuerySettings: FC<{ verticalSorters?: boolean; boxSx?: SxProps }> = ({ boxSx }) => {
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const selectedView = useContextSelector(ViewContext, ctx => ctx.views[viewId]);

  return (
    <Box sx={boxSx ?? { position: 'relative', maxWidth: '1200px' }}>
      <Stack
        direction="row"
        spacing={1}
        sx={[
          viewId &&
            !selectedView && {
              opacity: 0.25,
              pointerEvents: 'none'
            }
        ]}
      >
        <HitSort />
        <HitFilter />
        <SearchSpan />
      </Stack>
    </Box>
  );
};

export default memo(QuerySettings);

import { Box, Divider, Stack, type SxProps } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import { memo, type FC } from 'react';
import { useContextSelector } from 'use-context-selector';
import CustomSpan from './CustomSpan';
import HitFilter from './HitFilter';
import HitSort from './HitSort';
import SearchSpan from './SearchSpan';

const QuerySettings: FC<{ verticalSorters?: boolean; boxSx?: SxProps }> = ({ verticalSorters = false, boxSx }) => {
  const viewId = useContextSelector(HitSearchContext, ctx => ctx.viewId);
  const selectedView = useContextSelector(ViewContext, ctx => ctx.views?.find(val => val.view_id === viewId));

  return (
    <Box sx={boxSx ?? { position: 'relative', maxWidth: '1200px' }}>
      <Stack
        direction={verticalSorters ? 'column' : 'row'}
        justifyContent="space-between"
        spacing={1}
        divider={!verticalSorters && <Divider flexItem orientation="vertical" />}
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
        <SearchSpan useDefault={!selectedView?.span} />
      </Stack>

      <CustomSpan />
    </Box>
  );
};

export default memo(QuerySettings);

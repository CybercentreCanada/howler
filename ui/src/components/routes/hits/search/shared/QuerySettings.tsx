import { Add } from '@mui/icons-material';
import { Box, Chip, chipClasses, Stack, type SxProps } from '@mui/material';
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
        <SearchSpan />
        <HitFilter />
        <Chip
          variant="outlined"
          deleteIcon={<Add fontSize="small" />}
          onDelete={() => console.log('add')}
          sx={{ [`& > .${chipClasses.label}`]: { paddingRight: 0 } }}
        />
      </Stack>
    </Box>
  );
};

export default memo(QuerySettings);

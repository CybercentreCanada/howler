import { Add, ArrowDropDown } from '@mui/icons-material';
import { Box, Button, Grid, Stack, type SxProps } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { memo, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import HitFilter from './shared/HitFilter';
import HitSort from './shared/HitSort';
import SearchSpan from './shared/SearchSpan';
import ViewLink from './ViewLink';

const QuerySettings: FC<{ verticalSorters?: boolean; boxSx?: SxProps }> = ({ boxSx }) => {
  const { t } = useTranslation();

  const views = useContextSelector(ViewContext, ctx => ctx.views);
  const fetchViews = useContextSelector(ViewContext, ctx => ctx.fetchViews);
  const currentViews = useContextSelector(ParameterContext, ctx => ctx.views);
  const filters = useContextSelector(ParameterContext, ctx => ctx.filters);
  const addFilter = useContextSelector(ParameterContext, ctx => ctx.addFilter);
  const addView = useContextSelector(ParameterContext, ctx => ctx.addView);

  const allowAddViews = useMemo(
    () =>
      Object.values(views).filter(_view => !!_view && !currentViews?.includes(_view.view_id))?.length > 0 &&
      !currentViews?.includes(''),
    [views, currentViews]
  );

  const onAddView = async () => {
    await fetchViews();
    addView('');
  };

  return (
    <Box sx={boxSx ?? { position: 'relative', maxWidth: '1200px' }}>
      <Grid container spacing={1}>
        <Grid item>
          <HitSort />
        </Grid>
        <Grid item>
          <SearchSpan />
        </Grid>
        {currentViews?.map((view, id) => (
          <Grid item key={view}>
            <ViewLink id={id} viewId={view} />
          </Grid>
        ))}
        {filters?.map((filter, id) => (
          <Grid item key={filter}>
            <HitFilter id={id} value={filter} />
          </Grid>
        ))}
        <Grid item>
          <ChipPopper
            icon={<Add />}
            deleteIcon={<ArrowDropDown />}
            toggleOnDelete
            slotProps={{ chip: { size: 'small' } }}
          >
            <Stack spacing={1}>
              <Button
                id="add-filter"
                aria-label={t('hit.search.filter.add')}
                variant="outlined"
                onClick={() => addFilter('howler.assessment:*')}
              >
                <Add fontSize="small" />
                <span>{t('hit.search.filter.add')}</span>
              </Button>
              <Button
                id="add-view"
                aria-label={t('hit.search.view.add')}
                variant="outlined"
                onClick={onAddView}
                disabled={!allowAddViews}
              >
                <Add fontSize="small" />
                <span>{t('hit.search.view.add')}</span>
              </Button>
            </Stack>
          </ChipPopper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default memo(QuerySettings);

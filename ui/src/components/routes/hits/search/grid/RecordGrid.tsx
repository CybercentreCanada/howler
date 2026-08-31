import { Info } from '@mui/icons-material';
import { LinearProgress, Paper, Stack, TableBody, Typography, useTheme } from '@mui/material';
import { GridColumnsContext } from 'components/app/providers/GridColumnsProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import DevelopmentBanner from 'components/elements/display/features/DevelopmentBanner';
import AddColumnModal from 'components/elements/hit/grid/AddColumnModal';
import RecordTable from 'components/elements/hit/grid/RecordTable';
import RecordContextMenu from 'components/elements/record/RecordContextMenu';
import useRecordSelection from 'components/hooks/useRecordSelection';
import { uniq } from 'lodash-es';
import { useCallback, useContext, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import QuerySettings from '../QuerySettings';
import RecordQuery from '../RecordQuery';
import SearchActionMenu from '../shared/SearchActionMenu';

const RecordGrid: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const { onClick } = useRecordSelection();

  const search = useContextSelector(RecordSearchContext, ctx => ctx.search);
  const response = useContextSelector(RecordSearchContext, ctx => ctx.response);
  const searching = useContextSelector(RecordSearchContext, ctx => ctx.searching);

  const selectedHits = useContextSelector(RecordContext, ctx => ctx.selectedRecords);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const { columns, setColumns, isReady } = useContext(GridColumnsContext);

  const showSelectBar = useMemo(() => {
    if (selectedHits.length > 1) {
      return true;
    }

    if (selectedHits.length === 1 && selected && selectedHits[0]?.howler.id !== selected) {
      return true;
    }

    return false;
  }, [selected, selectedHits]);

  const onScroll = useCallback(
    (event: React.UIEvent<HTMLDivElement, UIEvent>) => {
      const target = event.target as HTMLDivElement;

      if (target.scrollHeight - target.scrollTop === target.clientHeight) {
        search(query!, true);
      }
    },
    [query, search]
  );

  const getSelectedId = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    const target = event.target as HTMLElement;
    const selectedElement = target.closest('[id]') as HTMLElement;

    if (!selectedElement) {
      return;
    }

    return selectedElement.id;
  }, []);

  return (
    <Stack
      spacing={1}
      p={2}
      width="100%"
      sx={{ overflow: 'hidden', height: `calc(100vh - ${theme.spacing(showSelectBar ? 13 : 8)})` }}
    >
      <DevelopmentBanner />
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography
          sx={{ color: 'text.secondary', fontSize: '0.9em', fontStyle: 'italic', mb: 0.5, textAlign: 'left' }}
          variant="body2"
        >
          {t('hit.search.prompt')}
        </Typography>
        <SearchActionMenu query={query!} />
      </Stack>
      <Stack direction="row" spacing={1}>
        <Stack position="relative" flex={1}>
          <RecordQuery searching={searching} triggerSearch={search} compact />
          {searching && (
            <LinearProgress
              sx={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                borderBottomLeftRadius: theme.shape.borderRadius,
                borderBottomRightRadius: theme.shape.borderRadius
              }}
            />
          )}
        </Stack>
      </Stack>
      <Stack direction="row" spacing={1} width="100%" alignItems="center">
        <QuerySettings boxSx={{ flex: 1 }} />
        <AddColumnModal columns={columns} addColumn={key => isReady && setColumns(uniq([...columns, key]))} />
      </Stack>
      {response && (
        <SearchTotal
          sx={{ color: 'text.secondary', fontSize: '0.9em', fontStyle: 'italic', mb: 0.5 }}
          variant="body2"
          offset={response.offset}
          pageLength={response.rows}
          total={response.total}
        />
      )}
      <Stack
        component={Paper}
        spacing={1}
        width="100%"
        height="100%"
        sx={{ overflow: 'auto', flex: 1 }}
        onScroll={onScroll}
      >
        <RecordTable
          query={query!}
          items={response?.items}
          refreshItems={search}
          ContextMenu={RecordContextMenu}
          contextMenuProps={{ Component: TableBody, getSelectedId }}
          onItemClick={onClick}
        />
        {(response?.total ?? 0) < 1 && (
          <Stack direction="row" spacing={1} alignItems="center" p={1} justifyContent="center" flex={1}>
            <Typography variant="h3" color="text.secondary" display="flex" flexDirection="row" alignItems="center">
              <Info fontSize="inherit" sx={{ color: 'text.secondary', mr: 1 }} />
              <span>{t('app.list.empty')}</span>
            </Typography>
          </Stack>
        )}
      </Stack>
    </Stack>
  );
};

export default RecordGrid;

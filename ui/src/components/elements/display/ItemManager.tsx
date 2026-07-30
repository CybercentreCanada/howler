import { Box, Fab, IconButton, LinearProgress, Stack, Tooltip, Typography, useMediaQuery } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import { useTranslation } from 'react-i18next';

import { Add, Search } from '@mui/icons-material';
import type { SearchResponseState } from 'components/app/providers/SearchResponseProvider';
import type { TuiListItemOnSelect, TuiListItemRenderer } from 'components/elements/addons/lists';
import { TuiList } from 'components/elements/addons/lists';
import SearchPagination from 'components/elements/addons/search/SearchPagination';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import type { ReactNode } from 'react';
import Phrase from '../addons/search/phrase/Phrase';

interface ItemManagerProps<T = unknown> {
  aboveSearch?: ReactNode;
  afterSearch?: ReactNode;
  belowSearch?: ReactNode;
  searchFilters?: ReactNode;
  hasError: boolean;
  onPageChange: (nextOffset: number) => void;
  onSearch: () => void;
  onCreate?: () => void;
  onSelect?: TuiListItemOnSelect<T>;
  phrase: string;
  renderer: TuiListItemRenderer<T>;
  response: SearchResponseState<T>;
  searchAdornment?: ReactNode;
  searching: boolean;
  createPrompt?: string;
  searchPrompt: string;
  setPhrase: (value: string) => void;
  createIcon?: ReactNode;
}

// eslint-disable-next-line comma-spacing
const ItemManager = <T = unknown,>({
  aboveSearch,
  afterSearch,
  belowSearch,
  searchFilters,
  hasError,
  onPageChange,
  onSearch,
  onSelect,
  onCreate,
  phrase,
  renderer,
  response,
  searchAdornment,
  searching,
  createPrompt,
  searchPrompt,
  setPhrase,
  createIcon
}: ItemManagerProps<T>) => {
  const { t } = useTranslation();
  const isNarrow = useMediaQuery('(max-width: 1800px)');

  return (
    <PageCenter maxWidth="1200px" textAlign="left" height="100%">
      <ErrorBoundary>
        <Stack spacing={1} sx={{ position: 'relative' }}>
          {aboveSearch}
          <Stack direction="row" spacing={1}>
            <Stack sx={{ flex: 1 }}>
              <Phrase
                value={phrase}
                onChange={setPhrase}
                onKeyDown={({ isEnter }) => {
                  if (isEnter) {
                    onSearch();
                  }
                }}
                error={hasError}
                InputProps={{
                  sx: {
                    pr: 1
                  }
                }}
                endAdornment={
                  <Stack direction="row" spacing={1}>
                    <Tooltip title={t(searchPrompt)}>
                      <IconButton onClick={() => onSearch()}>
                        <Search />
                      </IconButton>
                    </Tooltip>
                    {searchAdornment}
                  </Stack>
                }
              />
              {searching && (
                <LinearProgress
                  sx={theme => ({
                    mt: -0.5,
                    borderBottomLeftRadius: theme.shape.borderRadius,
                    borderBottomRightRadius: theme.shape.borderRadius
                  })}
                />
              )}
            </Stack>
            {afterSearch}
          </Stack>
          {searchFilters}
          {response && (
            <Stack direction="row" alignItems="center" mt={0.5}>
              <SearchTotal
                total={response.total}
                pageLength={response.items.length}
                offset={response.offset}
                sx={theme => ({ color: theme.palette.text.secondary, fontSize: '0.9em', fontStyle: 'italic' })}
              />
              <Box flex={1} />
              <SearchPagination
                total={response.total}
                limit={response.rows}
                offset={response.offset}
                removeCount={response.removeCount}
                onChange={onPageChange}
              />
            </Stack>
          )}
          {belowSearch}
          <TuiList onSelection={onSelect}>{renderer}</TuiList>
          {onCreate && (
            <Fab
              variant="extended"
              size="large"
              color="primary"
              sx={theme => ({
                textTransform: 'none',
                position: isNarrow ? 'fixed' : 'absolute',
                right: isNarrow ? theme.spacing(2) : `calc(100% + ${theme.spacing(5)})`,
                whiteSpace: 'nowrap',
                ...(isNarrow ? { bottom: theme.spacing(1) } : { top: 0 })
              })}
              onClick={onCreate}
            >
              {createIcon ?? <Add sx={{ mr: 1 }} />}
              <Typography>{t(createPrompt ?? 'create')}</Typography>
            </Fab>
          )}
        </Stack>
      </ErrorBoundary>
    </PageCenter>
  );
};

export default ItemManager;

import { Close, Search } from '@mui/icons-material';
import { Box, Chip, Grid, IconButton, LinearProgress, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import PageCenter from 'commons/components/pages/PageCenter';
import { parseEvent } from 'commons/components/utils/keyboard';
import VSBox from 'components/elements/addons/layout/vsbox/VSBox';
import VSBoxContent from 'components/elements/addons/layout/vsbox/VSBoxContent';
import VSBoxHeader from 'components/elements/addons/layout/vsbox/VSBoxHeader';
import type { TuiListItemOnSelect } from 'components/elements/addons/lists';
import { TuiListProvider } from 'components/elements/addons/lists';
import type { TuiTableCellRenderer, TuiTableColumn } from 'components/elements/addons/lists/table';
import TuiTable from 'components/elements/addons/lists/table/TuiTable';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import SearchPagination from 'components/elements/addons/search/SearchPagination';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { ChangeEvent, FC, KeyboardEvent } from 'react';
import { useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const COLUMN: TuiTableColumn[] = [
  { column: 'uname', i18nKey: 'page.user.search.column.username' },
  { column: 'name', i18nKey: 'page.user.search.column.fullname' },
  { column: 'email', i18nKey: 'page.user.search.column.email' }
];

const UserSearch: FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { load } = useContext<TuiListMethodsState<HowlerUser>>(TuiListMethodContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [searching, setSearching] = useState<boolean>(false);
  const [phrase, setPhrase] = useState('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<HowlerUser>>(null);

  // Search Handler.
  const onSearch = useCallback(async () => {
    setSearching(true);
    try {
      const sanitizedPhrase = sanitizeLuceneQuery(phrase);
      const _response = await dispatchApi(
        api.search.user.post({
          query: `name:*${sanitizedPhrase}* OR uname:*${sanitizedPhrase}* OR email:*${sanitizedPhrase}*`,
          rows: pageCount,
          offset
        })
      );
      setResponse(_response);
      load(_response.items.map(u => ({ id: u.username, item: u })));
    } finally {
      setSearching(false);
    }
  }, [dispatchApi, load, offset, pageCount, phrase]);

  const onPageChange = useCallback(
    (_offset: number) => {
      if (_offset !== offset) {
        searchParams.set('offset', _offset.toString());
        setSearchParams(searchParams);
        setOffset(_offset);
      }
    },
    [offset, searchParams, setSearchParams]
  );

  // Handler for when search term value changes.
  const onValueChange = useCallback((event: ChangeEvent<HTMLInputElement>) => setPhrase(event.target.value), []);

  // Handler for keyboard event in order to trigger search onEnter.
  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      const { isEnter } = parseEvent(event);
      if (isEnter) {
        onSearch();
      }
    },
    [onSearch]
  );

  // Clean button handler.
  const onClear = useCallback(() => {
    setPhrase('');
    onSearch();
  }, [onSearch]);

  // Effect to initialize list of users.
  useEffect(
    () => {
      onSearch();

      if (!searchParams.has('offset')) {
        searchParams.set('offset', '0');
        setSearchParams(searchParams);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    if (response?.total <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams);
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!searching) {
      onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  // TuiTable cell renderer
  const cellRenderer: TuiTableCellRenderer<HowlerUser> = useCallback((_value: string[], _, column) => {
    if (column.column !== 'groups') {
      return <div style={{ height: '100%', display: 'flex', alignItems: 'center' }}>{_value.toString()}</div>;
    } else {
      return (
        <Grid container spacing={1}>
          {_value.map(g => (
            <Grid key={g} item>
              <Chip label={g} size="small" sx={{ fontSize: '11px' }} />
            </Grid>
          ))}
        </Grid>
      );
    }
  }, []);

  // TuiTable handler for when selecting/clicking a Row.
  const onRowSelect: TuiListItemOnSelect<HowlerUser> = useCallback(
    selection => {
      navigate(selection.item.username);
    },
    [navigate]
  );

  return (
    <VSBox>
      <VSBoxHeader>
        <Typography
          sx={theme => ({ fontStyle: 'italic  ', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('page.user.search.prompt')}
        </Typography>
        <TextField
          fullWidth
          autoComplete="off"
          value={phrase}
          onChange={onValueChange}
          onKeyDown={onKeyDown}
          InputProps={{
            startAdornment: (
              <>
                <IconButton onClick={onSearch}>
                  <Search />
                </IconButton>
              </>
            ),
            endAdornment: (
              <>
                <IconButton onClick={onClear}>
                  <Close />
                </IconButton>
              </>
            )
          }}
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
              onChange={onPageChange}
            />
          </Stack>
        )}
      </VSBoxHeader>
      <VSBoxContent sx={{ mt: 1 }}>
        <TuiTable columns={COLUMN} onRowSelect={onRowSelect}>
          {cellRenderer}
        </TuiTable>
      </VSBoxContent>
    </VSBox>
  );
};

const UserSearchProvider: FC = () => {
  return (
    <PageCenter textAlign="left">
      <TuiListProvider>
        <UserSearch />
      </TuiListProvider>
    </PageCenter>
  );
};

export default UserSearchProvider;

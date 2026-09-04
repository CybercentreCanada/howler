import { Search } from '@mui/icons-material';
import { CircularProgress, IconButton, InputAdornment, Stack, TextField } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import IndexPicker from 'components/routes/hits/search/shared/IndexPicker';
import type { ChangeEvent, FC, KeyboardEvent } from 'react';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';

export type FuzzySearchBarProps = {
  onSearch: (query: string, indexes: string[]) => void;
  loading?: boolean;
};

const FuzzySearchBar: FC<FuzzySearchBarProps> = ({ onSearch, loading = false }) => {
  const { t } = useTranslation();
  const indexes = useContextSelector(ParameterContext, ctx => ctx.indexes);
  const defaultQuery = useContextSelector(ParameterContext, ctx => ctx.query);
  const [query, _setQuery] = useState(defaultQuery ?? '');
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const handleQueryChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      _setQuery(e.target.value);
    },
    [_setQuery]
  );

  const handleSearch = useCallback(() => {
    if (query.trim()) {
      setQuery(query.trim());
      onSearch(query.trim(), indexes ?? ['hit']);
    }
  }, [query, setQuery, onSearch, indexes]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        handleSearch();
      }
    },
    [handleSearch]
  );

  return (
    <Stack spacing={1}>
      <TextField
        id="fuzzy-search-input"
        size="small"
        fullWidth
        variant="outlined"
        placeholder={t('search.fuzzy.placeholder')}
        value={query}
        onChange={handleQueryChange}
        onKeyDown={handleKeyDown}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              {loading ? (
                <CircularProgress size={24} />
              ) : (
                <IconButton id="fuzzy-search-button" onClick={handleSearch} edge="end" disabled={!query.trim()}>
                  <Search />
                </IconButton>
              )}
            </InputAdornment>
          )
        }}
      />
      <Stack direction="row">
        <IndexPicker additionalOptions={[{ label: 'hit.search.index.case', value: 'case' }]} />
      </Stack>
    </Stack>
  );
};

export default FuzzySearchBar;

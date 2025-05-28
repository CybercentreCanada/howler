import { Alert, Box, Typography } from '@mui/material';
import api from 'api';
import type { AppSearchServiceState } from 'commons/components/app/AppContexts';
import type { AppSearchService } from 'commons/components/app/AppSearchService';
import HitQuickSearch from 'components/elements/hit/HitQuickSearch';
import type { Hit } from 'models/entities/generated/Hit';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import { useMyLocalStorageItem } from './useMyLocalStorage';

const useMySearch = (): AppSearchService<Hit> => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  return useMemo(
    () => ({
      onEnter: async (value: string, state: AppSearchServiceState<Hit>) => {
        state.set({ ...state, searching: true });
        //dispatchApi not available here since snackbarProvider isn't initialised yet

        try {
          const sanitizedValue = sanitizeLuceneQuery(value);
          const searchResult = await api.search.hit.post({
            offset: 0,
            rows: pageCount,
            query:
              `howler.assignment:*${sanitizedValue}* OR howler.analytic:*${sanitizedValue}* OR ` +
              `howler.detection:*${sanitizedValue}* OR howler.status:*${sanitizedValue}*`
          });

          state.set({
            ...state,
            searching: false,
            result: null,
            items: searchResult.items.map(r => ({ id: r.howler.id, item: r }))
          });
        } catch {
          state.set({ ...state, searching: false, result: { error: true }, items: null });
        }
      },
      onItemSelect: ({ item }) => {
        navigate(`/hits/${item.howler.id}`);
      },
      headerRenderer: (state: AppSearchServiceState<Hit>) =>
        (state.result?.error || !state.items) && (
          <Box sx={{ p: 1, pb: 0, textAlign: 'center' }}>
            {state.result?.error ? (
              <Alert severity="error" color="error">
                {t('hit.search.invalid')}
              </Alert>
            ) : (
              (!state.items || state.items.length === 0) && (
                <Typography sx={{ mb: -1, color: 'text.secondary' }}>{t('hit.quicksearch')}</Typography>
              )
            )}
          </Box>
        ),
      itemRenderer: (item, options) => {
        return (
          <Link
            to={`/hits/${item.id}`}
            style={{ flex: 1, textDecoration: 'none', color: 'inherit', overflow: 'hidden' }}
          >
            <HitQuickSearch hit={item.item} options={options} />
          </Link>
        );
      }
    }),
    [navigate, pageCount, t]
  );
};

export default useMySearch;

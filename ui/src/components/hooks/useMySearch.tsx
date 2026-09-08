import { Alert, Box, Typography } from '@mui/material';
import type { AppSearchItem, AppSearchItemRendererOption, AppSearchService, AppSearchServiceState } from '@tui/core';
import api from 'api';
import HitPreview from 'components/elements/hit/HitPreview';
import type { Hit } from 'models/entities/generated/Hit';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import { StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import { useMyLocalStorageItem } from './useMyLocalStorage';

const useMySearch = (): AppSearchService<Hit> => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];
  const [error, setError] = useState(false);

  return useMemo(
    () => ({
      onEnter: async (value: string, state?: AppSearchServiceState<Hit>) => {
        if (!state) {
          return;
        }

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

          if (!searchResult) {
            setError(true);
            state.set({ ...state, searching: false, items: [] });
            return;
          }

          setError(false);
          state.set({
            ...state,
            searching: false,
            items: searchResult.items.map(r => ({ id: r.howler.id, item: r }))
          });
        } catch {
          setError(true);
          state.set({ ...state, searching: false, items: [] });
        }
      },
      onItemSelect: ({ item }: AppSearchItem<Hit>) => {
        void navigate(`/hits/${item.howler.id}`);
      },
      headerRenderer: (state: AppSearchServiceState<Hit>) =>
        (error || !state.items) && (
          <Box sx={{ p: 1, pb: 0, textAlign: 'center' }}>
            {error ? (
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
      itemRenderer: (item: AppSearchItem<Hit>, options?: AppSearchItemRendererOption<Hit>) => {
        return (
          <Link
            to={`/hits/${item.id}`}
            style={{ flex: 1, textDecoration: 'none', color: 'inherit', overflow: 'hidden' }}
          >
            <HitPreview hit={item.item} options={options} />
          </Link>
        );
      }
    }),
    [error, navigate, pageCount, t]
  );
};

export default useMySearch;

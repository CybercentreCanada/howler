import { Article } from '@mui/icons-material';
import { Typography } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { TuiListProvider, type TuiListItem, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Overview } from 'models/entities/generated/Overview';
import { useCallback, useContext, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import OverviewCard from './OverviewCard';

const OverviewsBase: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();
  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<Overview>>(TuiListMethodContext);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<Overview>>(null);
  const [hasError, setHasError] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSearch = useCallback(async () => {
    try {
      setLoading(true);
      setHasError(false);

      if (phrase) {
        searchParams.set('phrase', phrase);
      } else {
        searchParams.delete('phrase');
      }
      setSearchParams(searchParams, { replace: true });

      // Check for the actual search query
      const query = phrase ? `*:*${phrase}*` : '*:*';
      // Ensure the overview should be visible and/or matches the type we are filtering for
      setResponse(
        await dispatchApi(
          api.search.overview.post({
            query,
            rows: pageCount,
            offset
          })
        )
      );
    } catch (e) {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  }, [phrase, setSearchParams, searchParams, dispatchApi, pageCount, offset]);

  // Load the items into list when response changes.
  // This hook should only trigger when the 'response' changes.
  useEffect(() => {
    if (response) {
      load(
        response.items.map((item: Overview) => ({
          id: item.overview_id,
          item,
          selected: false,
          cursor: false
        }))
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response, load]);

  const onPageChange = useCallback(
    (_offset: number) => {
      if (_offset !== offset) {
        searchParams.set('offset', _offset.toString());
        setSearchParams(searchParams, { replace: true });
        setOffset(_offset);
      }
    },
    [offset, searchParams, setSearchParams]
  );

  const onDelete = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement, MouseEvent>, id: string) => {
      e.preventDefault();
      e.stopPropagation();

      try {
        await dispatchApi(api.overview.del(id), { throwError: false, showError: true });
        await onSearch();
        showSuccessMessage(t('route.overviews.manager.delete.success'));
      } catch (_err) {
        // eslint-disable-next-line no-console
        console.warn(_err);
      }
    },
    [dispatchApi, onSearch, showSuccessMessage, t]
  );

  useEffect(() => {
    onSearch();

    if (!searchParams.has('offset')) {
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (response?.total <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!loading) {
      onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  const renderer = useCallback(
    (item: Overview, className?: string) => <OverviewCard overview={item} className={className} onDelete={onDelete} />,
    [onDelete]
  );

  return (
    <ItemManager
      onSearch={onSearch}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={loading}
      aboveSearch={
        <Typography
          sx={theme => ({ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('route.overviews.search.prompt')}
        </Typography>
      }
      renderer={({ item }: TuiListItemProps<Overview>, classRenderer) => renderer(item.item, classRenderer())}
      response={response}
      onSelect={(item: TuiListItem<Overview>) =>
        navigate(
          `/overviews/view?analytic=${item.item.analytic}${
            item.item.detection ? '&detection=' + item.item.detection : ''
          }`
        )
      }
      onCreate={() => navigate('/overviews/view')}
      createPrompt="route.overviews.create"
      searchPrompt="route.overviews.manager.search"
      createIcon={<Article sx={{ mr: 1 }} />}
    />
  );
};

const Overviews = () => {
  return (
    <TuiListProvider>
      <OverviewsBase />
    </TuiListProvider>
  );
};

export default Overviews;

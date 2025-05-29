import { Topic } from '@mui/icons-material';
import { Typography } from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { TuiListProvider, type TuiListItem, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Dossier } from 'models/entities/generated/Dossier';
import { useCallback, useContext, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import DossierCard from './DossierCard';

const DossiersBase: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();
  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<Dossier>>(TuiListMethodContext);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<Dossier>>(null);
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
          api.search.dossier.post({
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
        response.items.map((item: Dossier) => ({
          id: item.dossier_id,
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
        await dispatchApi(api.dossier.del(id), { throwError: false, showError: true });
        await onSearch();
        showSuccessMessage(t('route.dossiers.manager.delete.success'));
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
    (item: Dossier, className?: string) => <DossierCard dossier={item} className={className} onDelete={onDelete} />,
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
          {t('route.dossiers.search.prompt')}
        </Typography>
      }
      renderer={({ item }: TuiListItemProps<Dossier>, classRenderer) => renderer(item.item, classRenderer())}
      response={response}
      onSelect={(item: TuiListItem<Dossier>) => navigate(`/dossiers/${item.id}/edit`)}
      onCreate={() => navigate('/dossiers/create')}
      createPrompt="route.dossiers.create"
      searchPrompt="route.dossiers.manager.search"
      createIcon={<Topic sx={{ mr: 1 }} />}
    />
  );
};

const Dossiers = () => {
  return (
    <TuiListProvider>
      <DossiersBase />
    </TuiListProvider>
  );
};

export default Dossiers;

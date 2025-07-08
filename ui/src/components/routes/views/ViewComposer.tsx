import type { FC } from 'react';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { HelpOutline, Save } from '@mui/icons-material';
import {
  Alert,
  Checkbox,
  CircularProgress,
  Divider,
  LinearProgress,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import PageCenter from 'commons/components/pages/PageCenter';
import { HitContext } from 'components/app/providers/HitProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import CustomButton from 'components/elements/addons/buttons/CustomButton';
import FlexPort from 'components/elements/addons/layout/FlexPort';
import VSBox from 'components/elements/addons/layout/vsbox/VSBox';
import VSBoxContent from 'components/elements/addons/layout/vsbox/VSBoxContent';
import VSBoxHeader from 'components/elements/addons/layout/vsbox/VSBoxHeader';
import SearchTotal from 'components/elements/addons/search/SearchTotal';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Hit } from 'models/entities/generated/Hit';
import { useNavigate, useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import { convertDateToLucene } from 'utils/utils';
import ErrorBoundary from '../ErrorBoundary';
import HitQuery from '../hits/search/HitQuery';
import HitSort from '../hits/search/shared/HitSort';
import SearchSpan from '../hits/search/shared/SearchSpan';

const ViewComposer: FC = () => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage, showErrorMessage } = useMySnackbar();
  const routeParams = useParams();
  const navigate = useNavigate();

  const addView = useContextSelector(ViewContext, ctx => ctx.addView);
  const editView = useContextSelector(ViewContext, ctx => ctx.editView);
  const getCurrentView = useContextSelector(ViewContext, ctx => ctx.getCurrentView);

  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const loadHits = useContextSelector(HitContext, ctx => ctx.loadHits);

  // view state
  const [title, setTitle] = useState('');
  const [type, setType] = useState('global');
  const [advanceOnTriage, setAdvanceOnTriage] = useState(false);

  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);
  const sort = useContextSelector(ParameterContext, ctx => ctx.sort);
  const setSort = useContextSelector(ParameterContext, ctx => ctx.setSort);
  const span = useContextSelector(ParameterContext, ctx => ctx.span);
  const setSpan = useContextSelector(ParameterContext, ctx => ctx.setSpan);

  // Non-view state
  const [loading, setLoading] = useState(false);
  const [isSearchDirty, setIsSearchDirty] = useState(false);
  const [searching, setSearching] = useState<boolean>(false);
  const [error, setError] = useState<string>(null);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit>>();

  const onSave = useCallback(async () => {
    setLoading(true);

    try {
      if (!routeParams.id) {
        const newView = await addView({
          title,
          type,
          query,
          sort: sort || null,
          span: span || null,
          settings: {
            advance_on_triage: advanceOnTriage
          }
        });

        navigate(`/views/${newView.view_id}`);
      } else {
        await editView(routeParams.id, title, query, sort || null, span || null, advanceOnTriage);
      }

      showSuccessMessage(t(routeParams.id ? 'route.views.update.success' : 'route.views.create.success'));
    } catch (e) {
      showErrorMessage(e.message);
    } finally {
      setLoading(false);
    }
  }, [
    routeParams.id,
    showSuccessMessage,
    t,
    addView,
    title,
    type,
    query,
    sort,
    span,
    advanceOnTriage,
    navigate,
    editView,
    showErrorMessage
  ]);

  const search = useCallback(
    async (_query: string) => {
      setQuery(_query);

      setSearching(true);
      setError(null);

      try {
        const _response = await dispatchApi(
          api.search.hit.post({
            rows: pageCount,
            query: _query,
            sort,
            filters: span ? [`event.created:${convertDateToLucene(span)}`] : []
          }),
          { showError: false, throwError: true }
        );

        loadHits(_response.items);
        setResponse(_response);
      } catch (e) {
        setError(e.message);
      } finally {
        setSearching(false);
      }
    },
    [dispatchApi, loadHits, pageCount, setQuery, sort, span]
  );

  useEffect(() => {
    search(query || 'howler.id:*');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // We only run this when ancillary properties (i.e. filters, sorting) change
  useEffect(() => {
    if (query) {
      search(query);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort, span]);

  useEffect(() => {
    if (!routeParams.id) {
      return;
    }

    (async () => {
      const viewToEdit = await getCurrentView();

      if (!viewToEdit) {
        setError('route.views.missing');
        return;
      } else {
        setError(null);
      }

      setTitle(viewToEdit.title);
      setAdvanceOnTriage(viewToEdit.settings?.advance_on_triage ?? false);
      setQuery(viewToEdit.query);

      if (viewToEdit.sort) {
        setSort(viewToEdit.sort);
      }

      if (viewToEdit.span) {
        setSpan(viewToEdit.span);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeParams.id, getCurrentView]);

  return (
    <FlexPort>
      <ErrorBoundary>
        <PageCenter maxWidth="1500px" textAlign="left" height="100%">
          <VSBox top={0}>
            <VSBoxHeader pb={1}>
              <Stack spacing={1}>
                {error && (
                  <Alert variant="outlined" severity="error">
                    {t(error)}
                  </Alert>
                )}
                <Stack direction="row" spacing={1}>
                  <TextField
                    label={t('route.views.name')}
                    size="small"
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                    fullWidth
                  />
                  <ToggleButtonGroup
                    sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}
                    size="small"
                    exclusive
                    value={type}
                    onChange={(__, _type) => {
                      if (_type) {
                        setType(_type);
                      }
                    }}
                  >
                    <ToggleButton value="personal" aria-label="personal">
                      {t('route.views.manager.personal')}
                    </ToggleButton>
                    <ToggleButton value="global" aria-label="global">
                      {t('route.views.manager.global')}
                    </ToggleButton>
                  </ToggleButtonGroup>
                  <CustomButton
                    variant="outlined"
                    disabled={!title || !type || !query || !response || loading || searching || isSearchDirty}
                    startIcon={loading ? <CircularProgress size={20} /> : <Save />}
                    onClick={onSave}
                  >
                    {t('save')}
                  </CustomButton>
                </Stack>
                <Typography
                  sx={theme => ({
                    color: theme.palette.text.secondary,
                    fontSize: '0.9em',
                    fontStyle: 'italic',
                    mb: 0.5
                  })}
                  variant="body2"
                >
                  {t('hit.search.prompt')}
                </Typography>
                <HitQuery
                  triggerSearch={search}
                  searching={searching}
                  onChange={(_query, isDirty) => setIsSearchDirty(isDirty)}
                />
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{ '& > :not(.MuiDivider-root)': { flex: 1 } }}
                  divider={<Divider flexItem orientation="vertical" />}
                >
                  <HitSort />
                  <SearchSpan omitCustom />
                  <Stack
                    spacing={1}
                    direction="row"
                    alignItems="center"
                    sx={{ flex: '0 !important', minWidth: '300px' }}
                  >
                    <Typography component="span">{t('view.settings.advance_on_triage')}</Typography>
                    <Tooltip title={t('view.settings.advance_on_triage.description')}>
                      <HelpOutline sx={{ fontSize: '16px' }} />
                    </Tooltip>
                    <Checkbox
                      size="small"
                      checked={advanceOnTriage}
                      onChange={(_event, checked) => setAdvanceOnTriage(checked)}
                    />
                  </Stack>
                </Stack>
                {response?.total ? (
                  <SearchTotal
                    total={response.total}
                    pageLength={response.items.length}
                    offset={response.offset}
                    sx={theme => ({ color: theme.palette.text.secondary, fontSize: '0.9em', fontStyle: 'italic' })}
                  />
                ) : null}
                <LinearProgress sx={[!searching && { opacity: 0 }]} />
              </Stack>
            </VSBoxHeader>
            <VSBoxContent>
              <Stack spacing={1}>
                {!response?.total && <AppListEmpty />}
                {response?.items.map(hit => (
                  <HitCard key={hit.howler.id} id={hit.howler.id} layout={HitLayout.DENSE} />
                ))}
              </Stack>
            </VSBoxContent>
          </VSBox>
        </PageCenter>
      </ErrorBoundary>
    </FlexPort>
  );
};

export default ViewComposer;

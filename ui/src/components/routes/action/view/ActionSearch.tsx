import { Delete, Engineering, Terminal } from '@mui/icons-material';
import {
  Autocomplete,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { useAppUser } from 'commons/components/app/hooks';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import { TuiListProvider, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext } from 'components/elements/addons/lists/TuiListProvider';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Action } from 'models/entities/generated/Action';
import { useCallback, useContext, useEffect, useState, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey, VALID_ACTION_TRIGGERS } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import useMyActionFunctions from '../useMyActionFunctions';

const ActionSearch: FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const { dispatchApi } = useMyApi();
  const { load } = useContext(TuiListMethodContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const { deleteAction } = useMyActionFunctions();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [searching, setSearching] = useState<boolean>(false);
  const [hasError, setHasError] = useState(false);
  const [phrase, setPhrase] = useState(searchParams.get('phrase') || '');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [response, setResponse] = useState<HowlerSearchResponse<Action>>(null);
  const [searchModifiers, setSearchModifiers] = useState<string[]>([]);

  // Search Handler.
  const onSearch = useCallback(async () => {
    setSearching(true);
    setHasError(false);

    if (phrase) {
      searchParams.set('phrase', phrase);
    } else {
      searchParams.delete('phrase');
    }
    setSearchParams(searchParams, { replace: true });

    try {
      const sanitizedPhrase = sanitizeLuceneQuery(phrase);
      let query = `name:(*${sanitizedPhrase}*) OR query:(*${sanitizedPhrase}*)`;

      if (searchModifiers.length > 0) {
        query = `(${query}) AND (triggers:(${searchModifiers.join(' OR ')}))`;
      }

      const _response = await dispatchApi(
        api.search.action.post({
          query,
          rows: pageCount,
          offset
        })
      );
      setResponse(_response);
      load(_response.items.map(u => ({ id: u.action_id, item: u })));
    } catch (e) {
      setHasError(true);
    } finally {
      setSearching(false);
    }
  }, [dispatchApi, load, offset, pageCount, phrase, searchModifiers, searchParams, setSearchParams]);

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

  // Effect to initialize list of users.
  useEffect(
    () => {
      onSearch();

      if (!searchParams.has('offset')) {
        searchParams.set('offset', '0');
        setSearchParams(searchParams, { replace: true });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(() => {
    if (response?.total <= offset) {
      setOffset(0);
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
  }, [offset, response?.total, searchParams, setSearchParams]);

  useEffect(() => {
    if (!searching) {
      onSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset]);

  useEffect(() => {
    onSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchModifiers]);

  // Search result list item renderer.
  const renderer = useCallback(
    ({ item }: TuiListItemProps<Action>, classRenderer: () => string) => {
      return (
        <Card
          key={item.item.name}
          onClick={() => navigate(`/action/${item.item.action_id}`)}
          variant="outlined"
          className={classRenderer()}
          sx={{
            '&:hover': { borderColor: 'primary.main' },
            transitionProperty: 'border-color',
            cursor: 'pointer',
            mt: 1
          }}
        >
          <CardHeader
            title={
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="h5">{item.item.name}</Typography>
                {item.item.triggers.length > 0 && (
                  <Tooltip
                    title={
                      <Trans
                        i18nKey="route.actions.trigger.description"
                        values={{ triggers: item.item.triggers.join(', ') }}
                        components={{ bold: <strong /> }}
                      />
                    }
                  >
                    <Engineering />
                  </Tooltip>
                )}
                <FlexOne />
                {(item.item.owner_id === user.username || user.roles?.includes('admin')) && (
                  <IconButton
                    size="small"
                    onClick={async e => {
                      e.preventDefault();
                      e.stopPropagation();
                      await deleteAction(item.item.action_id);
                      onSearch();
                    }}
                  >
                    <Delete />
                  </IconButton>
                )}
                <HowlerAvatar
                  sx={{ width: 24, height: 24, marginRight: '8px !important' }}
                  userId={item.item.owner_id}
                />
              </Stack>
            }
            subheader={item.item.query}
          />
          <CardContent sx={{ paddingTop: 0 }}>
            <Grid container spacing={1}>
              {item.item.operations.map(d => (
                <Grid item key={d.operation_id}>
                  <Chip size="small" label={t(`operations.${d.operation_id}`)} />
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      );
    },
    [deleteAction, navigate, onSearch, t, user.roles, user.username]
  );

  return (
    <ItemManager
      onSearch={onSearch}
      onCreate={() => navigate('/action/execute')}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={searching}
      aboveSearch={
        <Typography
          sx={theme => ({ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('route.actions.search.prompt')}
        </Typography>
      }
      searchFilters={
        <Autocomplete
          multiple
          size="small"
          value={searchModifiers}
          onChange={(__, values) => setSearchModifiers(values)}
          getOptionLabel={trigger => t(`route.actions.trigger.${trigger}`)}
          options={VALID_ACTION_TRIGGERS}
          renderInput={params => (
            <TextField {...params} sx={{ maxWidth: '500px' }} label={t('route.actions.trigger')} />
          )}
        />
      }
      renderer={renderer}
      response={response}
      createPrompt="route.actions.create"
      searchPrompt="route.actions.search"
      createIcon={<Terminal sx={{ mr: 1 }} />}
    />
  );
};

const ActionSearchProvider: FC = () => {
  return (
    <TuiListProvider>
      <ActionSearch />
    </TuiListProvider>
  );
};

export default ActionSearchProvider;

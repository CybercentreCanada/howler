import { Article, KeyboardArrowDown } from '@mui/icons-material';
import {
  Box,
  Card,
  Collapse,
  IconButton,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import { useAppUser } from 'commons/components/app/hooks';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import { TuiListProvider, type TuiListItem, type TuiListItemProps } from 'components/elements/addons/lists';
import { TuiListMethodContext, type TuiListMethodsState } from 'components/elements/addons/lists/TuiListProvider';
import ItemManager from 'components/elements/display/ItemManager';
import useMyApi from 'components/hooks/useMyApi';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Template } from 'models/entities/generated/Template';
import { useCallback, useContext, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';
import TemplateCard from './TemplateCard';

const TemplatesBase: FC = () => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();
  const [searchParams, setSearchParams] = useSearchParams();
  const { load } = useContext<TuiListMethodsState<Template>>(TuiListMethodContext);
  const templates = useContextSelector(TemplateContext, ctx => ctx.templates);
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [phrase, setPhrase] = useState<string>('');
  const [offset, setOffset] = useState(parseInt(searchParams.get('offset')) || 0);
  const [showBuiltins, setShowBuiltins] = useState(true);
  const [response, setResponse] = useState<HowlerSearchResponse<Template>>(null);
  const [types, setTypes] = useState<('personal' | 'global')[]>([]);
  const [hasError, setHasError] = useState(false);
  const [searching, setSearching] = useState(false);

  const onSearch = useCallback(async () => {
    try {
      setSearching(true);
      setHasError(false);

      if (phrase) {
        searchParams.set('phrase', phrase);
      } else {
        searchParams.delete('phrase');
      }
      setSearchParams(searchParams, { replace: true });

      // Check for the actual search query
      const phraseQuery = phrase ? `*:*${phrase}*` : '*:*';
      // Ensure the template should be visible and/or matches the type we are filtering for
      const typeQuery = `(type:global OR owner:(${user.username} OR none)) AND type:(${types.join(' ') || '*'})`;

      setResponse(
        await dispatchApi(
          api.search.template.post({
            query: `${phraseQuery} AND ${typeQuery}`,
            rows: pageCount,
            offset
          })
        )
      );
    } catch (e) {
      setHasError(true);
    } finally {
      setSearching(false);
    }
  }, [phrase, setSearchParams, searchParams, user.username, types, dispatchApi, pageCount, offset]);

  // Load the items into list when response changes.
  // This hook should only trigger when the 'response' changes.
  useEffect(() => {
    if (response) {
      load(
        response.items.map((item: Template) => ({
          id: item.template_id,
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

  useEffect(() => {
    onSearch();

    if (!searchParams.has('offset')) {
      searchParams.set('offset', '0');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatchApi, types]);

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

  const builtInTemplates = useMemo(() => templates.filter(template => template.type === 'readonly'), [templates]);

  const renderer = useCallback(
    (item: Template, className?: string) => <TemplateCard template={item} className={className} />,
    []
  );

  return (
    <ItemManager
      onSearch={onSearch}
      onPageChange={onPageChange}
      phrase={phrase}
      setPhrase={setPhrase}
      hasError={hasError}
      searching={searching}
      searchFilters={
        <Stack direction="row" spacing={1} alignItems="center">
          <ToggleButtonGroup
            sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', alignSelf: 'start' }}
            size="small"
            value={types}
            onChange={(__, _types) => {
              if (_types) {
                setTypes(_types.length < 2 ? _types : []);
              }
            }}
          >
            <ToggleButton value="personal" aria-label="personal">
              {t('route.templates.manager.personal')}
            </ToggleButton>
            <ToggleButton value="global" aria-label="global">
              {t('route.templates.manager.global')}
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      }
      aboveSearch={
        <Typography
          sx={theme => ({ fontStyle: 'italic', color: theme.palette.text.disabled, mb: 0.5 })}
          variant="body2"
        >
          {t('route.templates.search.prompt')}
        </Typography>
      }
      belowSearch={
        types.length !== 1 &&
        offset < 1 &&
        builtInTemplates.length > 0 && (
          <Card sx={{ p: 1, mb: 1 }}>
            <Stack>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography>{t('route.templates.builtin.show')}</Typography>
                <Tooltip title={t(`route.templates.builtin.${showBuiltins ? 'hide' : 'show'}`)}>
                  <IconButton size="small" onClick={() => setShowBuiltins(!showBuiltins)}>
                    <KeyboardArrowDown
                      fontSize="small"
                      sx={{ transition: 'rotate 250ms', rotate: showBuiltins ? '180deg' : '0deg' }}
                    />
                  </IconButton>
                </Tooltip>
              </Stack>
              <Collapse in={showBuiltins}>
                <Box sx={{ mt: 1 }} />
                {builtInTemplates.map(template => renderer(template))}
              </Collapse>
            </Stack>
          </Card>
        )
      }
      renderer={({ item }: TuiListItemProps<Template>, classRenderer) => renderer(item.item, classRenderer())}
      response={response}
      onSelect={(item: TuiListItem<Template>) =>
        navigate(
          `/templates/view?type=${item.item.type}&analytic=${item.item.analytic}${
            item.item.detection ? '&detection=' + item.item.detection : ''
          }`
        )
      }
      onCreate={() => navigate('/templates/view')}
      createPrompt="route.templates.create"
      searchPrompt="route.templates.manager.search"
      createIcon={<Article sx={{ mr: 1 }} />}
    />
  );
};

const Templates = () => {
  return (
    <TuiListProvider>
      <TemplatesBase />
    </TuiListProvider>
  );
};

export default Templates;

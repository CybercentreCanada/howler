/* eslint-disable no-useless-escape */
import { useMonaco } from '@monaco-editor/react';
import { Alert, AlertTitle, Box, Stack, Typography, useMediaQuery, useTheme } from '@mui/material';
import { PageCenter, parseEvent } from '@tui/core';
import api from 'api';
import type { HowlerEQLSearchResponse, HowlerExplainSearchResponse, HowlerSearchResponse } from 'api/search';
import type { HowlerFacetSearchResponse } from 'api/search/facet';
import type { HowlerGroupedSearchResponse } from 'api/search/grouped';
import { FieldContext } from 'components/app/providers/FieldProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import JSONViewer from 'components/elements/display/json/JSONViewer';
import dayjs from 'dayjs';
import type { Hit } from 'models/entities/generated/Hit';
import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FC,
  type KeyboardEventHandler
} from 'react';
import { useTranslation } from 'react-i18next';
import { sanitizeMultilineLucene } from 'utils/stringUtils';
import { v4 as uuid } from 'uuid';
import {
  ExecuteQueryButton,
  FieldsControl,
  GroupByFieldSelect,
  type LuceneQueryType,
  LuceneQueryTypeSelect,
  OpenInSearchButton,
  QueryLanguageSelect,
  RowsControl,
  STEPS,
  type QueryLanguage
} from './QueryBuilderControls';
import QueryEditor from './QueryEditor';

const DEFAULT_VALUES = {
  eql: `sequence with maxspan=30m
  [ process where process.name == "regsvr32.exe" ]
  [ file where length(process.command_line) > 400 ]
`,
  lucene: `# Match any howler.id value
howler.id:*
AND
# Hits must be open
howler.status:open
`,
  yaml: `title: Example Howler Sigma Rule
id: ${uuid()}
status: test
description: A basic example of using sigma rule notation to query howler
references:
    - https://github.com/SigmaHQ/sigma
author: You
date: ${dayjs().format('YYYY/MM/DD')}
modified: ${dayjs().format('YYYY/MM/DD')}
tags:
    - attack.command_and_control
logsource:
    category: nbs
detection:
    selection1:
        howler.analytic|startswith:
            - '6Tail'
            - 'Assembly'
    selection2:
        howler.status:
          - open
          - in-progress
    condition: 1 of selection*
falsepositives:
    - Unknown
level: informational
`
};

type SearchResponse<T> =
  | HowlerSearchResponse<T>
  | HowlerEQLSearchResponse<T>
  | HowlerFacetSearchResponse
  | HowlerGroupedSearchResponse<T>;

const QueryBuilder: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const compactLayout = useMediaQuery('(max-width:870px)');
  const monaco = useMonaco();
  const { hitFields, getHitFields } = useContext(FieldContext);

  const [type, setType] = useState<QueryLanguage>('lucene');
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState(DEFAULT_VALUES.lucene);
  const [queryType, setQueryType] = useState<LuceneQueryType>('default');
  const [groupByField, setGroupByField] = useState<string>('');
  const [allFields, setAllFields] = useState(true);
  const [fields, setFields] = useState<string[]>(['howler.id']);
  const [response, setResponse] = useState<SearchResponse<Hit> | HowlerExplainSearchResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [rows, setRows] = useState(1);
  const [x, setX] = useState(0);

  const wrapper = useRef<HTMLDivElement>(null);

  const fieldOptions = useMemo(() => hitFields.map(_field => _field.key!), [hitFields]);

  const execute = useCallback(async () => {
    setLoading(true);

    try {
      const searchProperties = {
        fl: allFields ? undefined : fields.join(','),
        rows: STEPS[rows]
      };

      let result: SearchResponse<Hit> | HowlerExplainSearchResponse | undefined;
      if (type === 'lucene') {
        if (queryType === 'facet') {
          result = await api.search.facet.hit.post({
            query: sanitizeMultilineLucene(query),
            rows: STEPS[rows],
            fields
          });
        } else if (queryType === 'groupby') {
          result = await api.search.grouped.hit.post(groupByField, {
            query: sanitizeMultilineLucene(query),
            ...searchProperties
          });
        } else if (queryType === 'explain') {
          result = await api.search.hit.explain.post({
            query: sanitizeMultilineLucene(query)
          });
        } else {
          result = await api.search.hit.post({
            query: sanitizeMultilineLucene(query),
            ...searchProperties
          });
        }
      } else if (type === 'eql') {
        result = await api.search.hit.eql.post({
          eql_query: sanitizeMultilineLucene(query),
          ...searchProperties
        });
      } else {
        result = await api.search.hit.sigma.post({
          sigma: query,
          ...searchProperties
        });
      }

      setError('');
      if (!result) {
        setResponse(null);
        return;
      }

      setResponse(result);
    } catch (e) {
      setError(e instanceof Error ? (e.message ?? e.toString()) : String(e));
    } finally {
      setLoading(false);
    }
  }, [allFields, fields, groupByField, query, queryType, rows, type]);

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = useCallback(
    event => {
      const parsedEvent = parseEvent(event);

      if (parsedEvent.isCtrl && parsedEvent.isEnter) {
        void execute();
      }
    },
    [execute]
  );

  const onMouseMove = useCallback((event: MouseEvent) => {
    const wrapperRect = wrapper.current?.getBoundingClientRect();

    if (!wrapperRect) {
      return;
    }

    const offset = event.clientX - (wrapperRect.left + wrapperRect.width / 2);

    setX(offset);
  }, []);

  const onMouseUp = useCallback(() => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onMouseDown = useCallback(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [onMouseMove, onMouseUp]);

  const searchDisabled = useMemo(
    () => type === 'lucene' && queryType === 'groupby' && !groupByField,
    [groupByField, queryType, type]
  );

  useEffect(() => {
    if (type !== 'lucene' && queryType !== 'default') {
      setQueryType('default');
    }
  }, [queryType, type]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    const queryDisposable = monaco.editor.addEditorAction({
      id: 'execute-query',
      label: t('route.advanced.execute.query'),
      contextMenuGroupId: 'howler',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: execute
    });

    return () => {
      queryDisposable.dispose();
    };
  }, [execute, monaco, t]);

  useEffect(() => {
    void getHitFields();
  }, [getHitFields]);

  useEffect(() => {
    setResponse(null);

    if (!monaco) {
      return;
    }

    monaco.editor.getModels().forEach(model => {
      model.setValue(DEFAULT_VALUES[type]);
    });
  }, [type, monaco]);

  return (
    <PageCenter width="100%" maxWidth="100%" margin={0} textAlign="left">
      <Stack ref={wrapper}>
        <Stack
          direction="row"
          spacing={1}
          sx={{
            px: 2,
            pt: 1,
            pb: 1,
            // Fix TuiButton Issue
            '& > span': {
              display: 'flex',
              alignSelf: 'stretch'
            }
          }}
        >
          <ExecuteQueryButton loading={loading} searchDisabled={searchDisabled} onExecute={execute} />
          <Stack direction={compactLayout ? 'column' : 'row'} spacing={1}>
            <QueryLanguageSelect value={type} onChange={setType} compactLayout={compactLayout} />
            <RowsControl value={rows} onChange={setRows} />
          </Stack>
          {type === 'lucene' && <LuceneQueryTypeSelect value={queryType} onChange={setQueryType} />}
          {queryType === 'groupby' && (
            <GroupByFieldSelect
              options={fieldOptions}
              value={groupByField}
              onChange={setGroupByField}
              onKeyDown={onKeyDown}
            />
          )}
          <FieldsControl
            allFields={allFields}
            onAllFieldsChange={setAllFields}
            queryType={queryType}
            fieldOptions={fieldOptions}
            fields={fields}
            onFieldsChange={setFields}
            onKeyDown={onKeyDown}
          />
          <FlexOne />
          {type === 'lucene' && <OpenInSearchButton query={query} hasResponse={!!response} />}
        </Stack>
        <Box
          width="100%"
          height="calc(100vh - 112px)"
          sx={{ position: 'relative', overflow: 'hidden', borderTop: `thin solid ${theme.palette.divider}` }}
        >
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              bottom: 0,
              right: `calc(50% + 7px - ${x}px)`,
              pt: 1,
              display: 'flex'
            }}
          >
            <QueryEditor query={query} setQuery={setQuery} language={type} height="100%" />
          </Box>
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: 'calc(50% - 5px)',
              width: '10px',
              backgroundColor: theme.palette.divider,
              cursor: 'col-resize',
              transform: `translateX(${x}px)`,
              zIndex: 1000,
              borderRadius: theme.shape.borderRadius
            }}
            onMouseDown={onMouseDown}
          />
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: `calc(50% + 7px + ${x}px)`,
              bottom: 0,
              right: 0,
              display: 'flex',
              alignItems: 'stretch',
              justifyContent: 'stretch',
              px: 1,
              pt: 1,
              mt: -1,
              '& > *': { width: '100%' },
              '& .react-json-view': {
                backgroundColor: `${theme.palette.background.paper} !important`
              }
            }}
          >
            {response ? (
              <JSONViewer data={response ?? {}} collapse={allFields} />
            ) : (
              <Stack alignItems="center" p={2}>
                <Typography variant="h3" sx={{ mt: 4, color: 'text.secondary', opacity: 0.7 }}>
                  {t('route.advanced.result.title')}
                </Typography>
                <Typography variant="h5" sx={{ mt: 2, color: 'text.secondary', opacity: 0.7 }}>
                  {t('route.advanced.result.description')}
                </Typography>
              </Stack>
            )}
          </Box>
          {error && (
            <Alert
              sx={{ position: 'absolute', bottom: 0, left: 0, right: '50%', m: 1, mr: 13, maxHeight: '40vh' }}
              variant="outlined"
              color="error"
            >
              <AlertTitle>{t('route.advanced.error')}</AlertTitle>
              {error}
            </Alert>
          )}
        </Box>
      </Stack>
    </PageCenter>
  );
};

export default QueryBuilder;

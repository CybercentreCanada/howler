/* eslint-disable no-useless-escape */
import { useMonaco } from '@monaco-editor/react';
import { OpenInNew, PlayArrowOutlined, SsidChart } from '@mui/icons-material';
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  FormControlLabel,
  IconButton,
  ListItemText,
  Slider,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import Popper, { type PopperProps } from '@mui/material/Popper';
import api from 'api';
import type { HowlerEQLSearchResponse, HowlerSearchResponse } from 'api/search';
import type { HowlerFacetSearchResponse } from 'api/search/facet';
import type { HowlerGroupedSearchResponse } from 'api/search/grouped';
import PageCenter from 'commons/components/pages/PageCenter';
import { parseEvent } from 'commons/components/utils/keyboard';
import { FieldContext } from 'components/app/providers/FieldProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import CustomButton from 'components/elements/addons/buttons/CustomButton';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import JSONViewer from 'components/elements/display/json/JSONViewer';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Hit } from 'models/entities/generated/Hit';
import moment from 'moment';
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
import { Link } from 'react-router-dom';
import { sanitizeMultilineLucene } from 'utils/stringUtils';
import { v4 as uuid } from 'uuid';
import QueryEditor from './QueryEditor';
import RuleModal from './RuleModal';

const QUERY_TYPES = ['eql', 'lucene', 'yaml'];

const STEPS = [1, 5, 25, 50, 100, 250, 500, 1000, 2500, 10000];

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
date: ${moment().format('YYYY/MM/DD')}
modified: ${moment().format('YYYY/MM/DD')}
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

const LUCENE_QUERY_OPTIONS = ['default', 'facet', 'groupby'];

type SearchResponse<T> =
  | HowlerSearchResponse<T>
  | HowlerEQLSearchResponse<T>
  | { [index: string]: HowlerFacetSearchResponse }
  | HowlerGroupedSearchResponse<T>;

const CustomPopper = (props: PopperProps) => {
  return <Popper {...props} style={{ width: 'fit-content' }} placement="bottom-start" />;
};

const QueryBuilder: FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const smallButtons = useMediaQuery('(max-width:1150px)');
  const compactLayout = useMediaQuery('(max-width:870px)');
  const monaco = useMonaco();
  const { hitFields, getHitFields } = useContext(FieldContext);
  const { showModal } = useContext(ModalContext);
  const { showWarningMessage } = useMySnackbar();

  const [type, setType] = useState<'eql' | 'lucene' | 'yaml'>('lucene');
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState(DEFAULT_VALUES.lucene);
  const [queryType, setQueryType] = useState(LUCENE_QUERY_OPTIONS[0]);
  const [groupByField, setGroupByField] = useState(null);
  const [allFields, setAllFields] = useState(true);
  const [fields, setFields] = useState<string[]>(['howler.id']);
  const [response, setResponse] = useState<SearchResponse<Hit>>(null);
  const [error, setError] = useState<string>(null);
  const [rows, setRows] = useState(1);
  const [x, setX] = useState(0);

  const wrapper = useRef<HTMLDivElement>();

  const fieldOptions = useMemo(() => hitFields.map(_field => _field.key), [hitFields]);

  const execute = useCallback(async () => {
    setLoading(true);

    try {
      const searchProperties = {
        fl: allFields ? null : fields.join(','),
        rows: STEPS[rows]
      };

      let result: SearchResponse<Hit>;
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

      setResponse(result);
      setError(null);
    } catch (e) {
      setError(e.message ?? e.toString());
    } finally {
      setLoading(false);
    }
  }, [allFields, fields, groupByField, query, queryType, rows, type]);

  const onKeyDown: KeyboardEventHandler<HTMLDivElement> = useCallback(
    event => {
      const parsedEvent = parseEvent(event);

      if (parsedEvent.isCtrl && parsedEvent.isEnter) {
        execute();
      }
    },
    [execute]
  );

  const onMouseMove = useCallback((event: MouseEvent) => {
    const wrapperRect = wrapper.current?.getBoundingClientRect();

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

  const onCreateRule = useCallback(async () => {
    if (!response) {
      showWarningMessage(t('route.advanced.create.rule.disabled'));
      return;
    }

    await new Promise<void>(res =>
      showModal(<RuleModal onSubmit={res} fileData={query} type={type} />, {
        maxWidth: '85vw',
        maxHeight: '85vh'
      })
    );
  }, [query, response, showModal, showWarningMessage, t, type]);

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

    const ruleDisposable = monaco.editor.addEditorAction({
      id: 'save-query',
      label: t('route.advanced.create.rule'),
      contextMenuGroupId: 'howler',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
      run: onCreateRule
    });

    return () => {
      queryDisposable.dispose();
      ruleDisposable.dispose();
    };
  }, [execute, monaco, onCreateRule, t]);

  useEffect(() => {
    getHitFields();
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
          {smallButtons ? (
            <Tooltip title={t('route.actions.execute')}>
              <IconButton
                size="small"
                sx={{ alignSelf: 'start' }}
                color="success"
                onClick={execute}
                disabled={searchDisabled}
              >
                {loading ? (
                  <CircularProgress size={18} color="success" />
                ) : (
                  <PlayArrowOutlined color={searchDisabled ? 'disabled' : 'success'} />
                )}
              </IconButton>
            </Tooltip>
          ) : (
            <CustomButton
              size="small"
              variant="outlined"
              startIcon={
                loading ? (
                  <CircularProgress size={18} color="success" />
                ) : (
                  <PlayArrowOutlined
                    color={searchDisabled ? 'disabled' : 'success'}
                    sx={{ '& path': { stroke: 'currentcolor', strokeWidth: '1px' } }}
                  />
                )
              }
              color="success"
              onClick={execute}
              disabled={searchDisabled}
            >
              {t('route.actions.execute')}
            </CustomButton>
          )}
          <Stack direction={compactLayout ? 'column' : 'row'} spacing={1}>
            <Autocomplete
              value={type}
              onChange={(__, value) => setType(value as 'eql' | 'lucene' | 'yaml')}
              options={QUERY_TYPES}
              getOptionLabel={option => t(`route.advanced.query.${option}`)}
              renderOption={(props, option) => (
                <ListItemText
                  {...(props as any)}
                  sx={{ flexDirection: 'column', alignItems: 'start !important' }}
                  primary={t(`route.advanced.query.${option}`)}
                  secondary={t(`route.advanced.query.${option}.description`)}
                />
              )}
              renderInput={params => (
                <TextField {...params} size="small" label={t('route.advanced.type')} sx={{ minWidth: '250px' }} />
              )}
              sx={[
                !compactLayout && {
                  height: '100%',
                  '& .MuiFormControl-root': { height: '100%', '& > div': { height: '100%' } }
                }
              ]}
              slotProps={{ paper: { sx: { minWidth: '600px' } } }}
            />
            <Card variant="outlined" sx={{ flex: 1, maxWidth: '350px', minWidth: '210px' }}>
              <Stack spacing={0.5} sx={{ px: 1, alignItems: 'start' }}>
                <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                  {t('route.advanced.rows')}: {STEPS[rows]}
                </Typography>
                <Slider
                  size="small"
                  valueLabelDisplay="off"
                  value={rows}
                  onChange={(_, value) => setRows(value as number)}
                  min={0}
                  max={9}
                  step={1}
                  marks
                  track={false}
                  sx={{ py: 0.5 }}
                />
              </Stack>
            </Card>
          </Stack>
          {type === 'lucene' && (
            <Autocomplete
              size="small"
              getOptionLabel={opt => t(`route.advanced.query.type.${opt}`)}
              options={LUCENE_QUERY_OPTIONS}
              value={queryType}
              onChange={(_event, value) => setQueryType(value)}
              renderInput={params => (
                <TextField {...params} label={t('route.advanced.query.type')} sx={{ minWidth: '200px' }} />
              )}
            />
          )}
          {queryType === 'groupby' && (
            <Autocomplete
              size="small"
              options={fieldOptions}
              value={groupByField}
              onChange={(__, value) => setGroupByField(value)}
              renderInput={params => <TextField {...params} label={t('route.advanced.pivot.field')} />}
              sx={{ minWidth: '200px', '& label': { zIndex: 1200 } }}
              onKeyDown={onKeyDown}
              PopperComponent={CustomPopper}
            />
          )}
          {allFields && queryType !== 'facet' ? (
            <FormControlLabel
              control={<Checkbox size="small" checked={allFields} onChange={(__, checked) => setAllFields(checked)} />}
              label={t('route.advanced.fields.all')}
              sx={{ '& > span': { color: 'text.secondary' }, alignSelf: 'start' }}
            />
          ) : (
            <Autocomplete
              fullWidth
              renderTags={values =>
                values.length <= 3 ? (
                  <Stack direction="row" spacing={0.5}>
                    {values.map(_value => (
                      <Chip size="small" key={_value} label={_value} />
                    ))}
                  </Stack>
                ) : (
                  <Tooltip
                    title={
                      <Stack spacing={1}>
                        {values.map(_value => (
                          <span key={_value}>{_value}</span>
                        ))}
                      </Stack>
                    }
                  >
                    <Chip size="small" label={values.length} />
                  </Tooltip>
                )
              }
              multiple
              size="small"
              options={fieldOptions}
              value={fields}
              onChange={(__, values) => (values.length > 0 ? setFields(values) : setAllFields(true))}
              renderInput={params => <TextField {...params} label={t('route.advanced.fields')} />}
              sx={{ maxWidth: '500px', width: '20vw', minWidth: '200px', '& label': { zIndex: 1200 } }}
              onKeyDown={onKeyDown}
              PopperComponent={CustomPopper}
            />
          )}
          <FlexOne />
          {type === 'lucene' &&
            (smallButtons ? (
              <Tooltip title={t('route.advanced.open')}>
                <IconButton
                  color="primary"
                  sx={{ alignSelf: 'center' }}
                  component={Link}
                  disabled={!response}
                  to={`/hits?query=${sanitizeMultilineLucene(query).replaceAll('\n', ' ').trim()}`}
                >
                  <OpenInNew fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : (
              <CustomButton
                size="small"
                variant="outlined"
                startIcon={<OpenInNew />}
                component={Link}
                disabled={!response}
                // TuiButton doesn't accept this prop even through the underlying component does, so we do a hack
                {...({ to: `/hits?query=${sanitizeMultilineLucene(query).replaceAll('\n', ' ').trim()}` } as any)}
              >
                {t('route.advanced.open')}
              </CustomButton>
            ))}
          {smallButtons ? (
            <Tooltip title={response ? t('route.advanced.create.rule') : t('route.advanced.create.rule.disabled')}>
              <IconButton
                size="small"
                sx={{ alignSelf: 'center' }}
                color="info"
                onClick={onCreateRule}
                disabled={!response}
              >
                <SsidChart />
              </IconButton>
            </Tooltip>
          ) : (
            <CustomButton
              size="small"
              variant="outlined"
              color="info"
              startIcon={<SsidChart />}
              onClick={onCreateRule}
              disabled={!response}
              // TuiButton doesn't accept this prop even through the underlying component does, so we do a hack
              {...({ to: `/hits?query=${sanitizeMultilineLucene(query).replaceAll('\n', ' ').trim()}` } as any)}
              tooltip={!response && t('route.advanced.create.rule.disabled')}
            >
              {t('route.advanced.create.rule')}
            </CustomButton>
          )}
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

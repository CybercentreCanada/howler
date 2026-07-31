import { useMonaco } from '@monaco-editor/react';
import { CheckCircleOutline, FilterList, RadioButtonUnchecked, Search } from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import ChipPopper from 'components/elements/display/ChipPopper';
import QueryResultText from 'components/elements/display/QueryResultText';
import useMyApi from 'components/hooks/useMyApi';
import QueryEditor from 'components/routes/advanced/QueryEditor';
import type { Hit } from 'models/entities/generated/Hit';
import type { Rule } from 'models/entities/generated/Rule';
import type { editor, IDisposable } from 'monaco-editor';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const DEFAULT_TIMEFRAME_DAYS = 14;
const PROMPT_CONTEXT =
  'isRecordQuery && !suggestWidgetVisible && !renameInputVisible && !inSnippetMode && !quickFixWidgetVisible';

interface CreateRuleDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (ruleData: Partial<Rule>) => Promise<void>;
}

const OPTIONS: editor.IStandaloneEditorConstructionOptions = {
  fontSize: 17,
  lineHeight: 19,
  lineNumbers: 'off',
  lineDecorationsWidth: 0,
  lineNumbersMinChars: 0,
  showFoldingControls: 'never',
  scrollBeyondLastLine: false,
  glyphMargin: false,
  renderLineHighlight: 'none',
  overviewRulerLanes: 0
};

const INDEX_OPTIONS = ['hit', 'event'] as const;

const Subtitle: FC<{ i18nKey: string }> = ({ i18nKey }) => {
  const { t } = useTranslation();

  return (
    <Typography
      sx={theme => ({
        color: theme.palette.text.secondary,
        fontSize: '0.9em',
        fontStyle: 'italic'
      })}
      variant="body2"
    >
      {t(i18nKey)}
    </Typography>
  );
};

const CreateRuleDialog: FC<CreateRuleDialogProps> = ({ open, onClose, onSubmit }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const monaco = useMonaco();

  const [query, setQuery] = useState('');
  const [destination, setDestination] = useState('');
  const [indexes, setIndexes] = useState<('hit' | 'event')[]>(['hit']);
  const [timeframeDays, setTimeframeDays] = useState<number>(DEFAULT_TIMEFRAME_DAYS);
  const [hasExpiry, setHasExpiry] = useState(true);
  const [expireAfterResolved, setExpireAfterResolved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit> | null>(null);

  const handleOpen = useCallback(() => {
    setQuery('');
    setDestination('');
    setIndexes(['hit']);
    setTimeframeDays(DEFAULT_TIMEFRAME_DAYS);
    setHasExpiry(true);
    setExpireAfterResolved(false);
    setResponse(null);
  }, []);

  const handleSearch = useCallback(async () => {
    setSearching(true);
    try {
      const result = await dispatchApi(
        api.search.hit.post({
          query,
          rows: 0,
          track_total_hits: true
        })
      );
      setResponse(result);
    } finally {
      setSearching(false);
    }
  }, [dispatchApi, query]);

  const handleQueryChange = useCallback((q: string) => {
    setQuery(q);
    setResponse(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!query.trim() || !destination.trim()) {
      return;
    }

    setLoading(true);
    try {
      await onSubmit({
        query: query.trim(),
        destination: destination.trim(),
        timeframe: hasExpiry ? timeframeDays : undefined,
        expire_after_resolved: hasExpiry ? expireAfterResolved : false,
        indexes
      });

      onClose();
    } finally {
      setLoading(false);
    }
  }, [query, destination, hasExpiry, timeframeDays, expireAfterResolved, indexes, onSubmit, onClose]);

  const onMount = useCallback((ed: editor.IStandaloneCodeEditor) => {
    ed.createContextKey('isRecordQuery', true);
  }, []);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    const executeDisposable = monaco.editor.addEditorAction({
      id: 'execute-query',
      label: t('route.advanced.execute.query'),
      contextMenuGroupId: 'howler',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: handleSearch
    });

    return () => {
      executeDisposable.dispose();
    };
  }, [monaco, t, handleSearch]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    let disposable: IDisposable;
    disposable = monaco.editor.addKeybindingRule({
      command: 'execute-query',
      keybinding: monaco.KeyCode.Enter,
      when: PROMPT_CONTEXT
    });

    return () => {
      disposable.dispose();
    };
  }, [monaco, handleSearch]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      id="create-rule-dialog"
      TransitionProps={{ onEnter: handleOpen }}
      PaperProps={{
        elevation: 0
      }}
    >
      <DialogTitle>{t('page.cases.rules.create')}</DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ mt: 1 }}>
          <Box>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="subtitle2" gutterBottom>
                {t('page.cases.rules.query')}
              </Typography>
              <ChipPopper
                icon={<FilterList fontSize="small" />}
                label={indexes.map(opt => t(`hit.search.index.${opt}`)).join(', ')}
                minWidth="225px"
                slotProps={{ chip: { size: 'small' } }}
              >
                <Autocomplete
                  size="small"
                  multiple
                  options={INDEX_OPTIONS}
                  value={indexes}
                  onChange={(_ev, values) => values.length > 0 && setIndexes(values)}
                  getOptionLabel={opt => t(`hit.search.index.${opt}`)}
                  renderInput={params => <TextField {...params} />}
                />
              </ChipPopper>
            </Stack>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, flex: 1 }}>
                <Card
                  variant="outlined"
                  sx={theme => ({
                    width: '100%',
                    height: theme.spacing(5),
                    py: 1,
                    pl: 1,
                    pr: 0.5,
                    position: 'relative',
                    overflow: 'visible',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    '& .monaco-editor': {
                      position: 'absolute !important'
                    },
                    transition: theme.transitions.create('border-color')
                  })}
                  onKeyDown={e => e.stopPropagation()}
                >
                  <QueryEditor
                    query={query}
                    setQuery={handleQueryChange}
                    language="lucene"
                    id="rule-query-editor"
                    height="20px"
                    editorOptions={OPTIONS}
                    onMount={onMount}
                  />

                  <Tooltip title={t('route.search')}>
                    <span>
                      <IconButton
                        size="small"
                        id="rule-search-button"
                        onClick={handleSearch}
                        disabled={searching || !query.trim()}
                      >
                        <Search />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Card>
              </Box>
            </Stack>
            {response ? (
              <QueryResultText count={response.total} query={query} mb={0} />
            ) : (
              <Subtitle i18nKey="hit.search.prompt" />
            )}
          </Box>

          <Box>
            <TextField
              id="rule-destination-input"
              label={t('page.cases.rules.destination')}
              value={destination}
              onChange={e => setDestination(e.target.value)}
              fullWidth
              placeholder="alerts/{{howler.analytic}}"
              size="small"
            />
            <Subtitle i18nKey="page.cases.rules.destination.help" />
          </Box>

          <Stack>
            <TextField
              id="rule-timeframe-input"
              type="number"
              label={t('page.cases.rules.timeframe')}
              value={timeframeDays}
              onChange={e => setTimeframeDays(Math.max(1, parseInt(e.target.value, 10) || 1))}
              size="small"
              disabled={!hasExpiry}
              sx={{ flex: 1 }}
              InputProps={{ inputProps: { min: 1 } }}
            />
            <Subtitle i18nKey="page.cases.rules.timeframe.help" />
          </Stack>

          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Chip
              id="rule-no-expiry-checkbox"
              label={t('page.cases.rules.no_expiry')}
              icon={!hasExpiry ? <CheckCircleOutline /> : <RadioButtonUnchecked />}
              variant="filled"
              color={!hasExpiry ? 'primary' : 'default'}
              clickable
              disabled={expireAfterResolved}
              onClick={() => setHasExpiry(prev => !prev)}
            />
            <Chip
              id="rule-expire-after-resolved"
              label={t('page.cases.rules.expire_after_resolved')}
              icon={expireAfterResolved ? <CheckCircleOutline /> : <RadioButtonUnchecked />}
              variant="filled"
              color={expireAfterResolved ? 'primary' : 'default'}
              clickable={hasExpiry}
              onClick={() => setExpireAfterResolved(prev => !prev)}
              disabled={!hasExpiry}
            />
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t('cancel')}</Button>
        <Button
          id="rule-submit-button"
          variant="contained"
          onClick={handleSubmit}
          disabled={!response || loading || !query.trim() || !destination.trim() || indexes.length === 0}
        >
          {t('page.cases.rules.create')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateRuleDialog;

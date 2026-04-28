import { useMonaco } from '@monaco-editor/react';
import { Search } from '@mui/icons-material';
import {
  Box,
  Button,
  Card,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  FormGroup,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import QueryResultText from 'components/elements/display/QueryResultText';
import useMyApi from 'components/hooks/useMyApi';
import QueryEditor from 'components/routes/advanced/QueryEditor';
import dayjs, { type Dayjs } from 'dayjs';
import type { Hit } from 'models/entities/generated/Hit';
import type { Rule } from 'models/entities/generated/Rule';
import type { editor, IDisposable } from 'monaco-editor';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';

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

const CreateRuleDialog: FC<CreateRuleDialogProps> = ({ open, onClose, onSubmit }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const monaco = useMonaco();

  const [query, setQuery] = useState('');
  const [destination, setDestination] = useState('');
  const [indexes, setIndexes] = useState<('hit' | 'observable')[]>(['hit']);
  const [timeframe, setTimeframe] = useState<Dayjs>(dayjs().add(DEFAULT_TIMEFRAME_DAYS, 'day'));
  const [noExpiry, setNoExpiry] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [response, setResponse] = useState<HowlerSearchResponse<Hit> | null>(null);

  const handleOpen = useCallback(() => {
    setQuery('');
    setDestination('');
    setIndexes(['hit']);
    setTimeframe(dayjs().add(DEFAULT_TIMEFRAME_DAYS, 'day'));
    setNoExpiry(false);
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
        timeframe: noExpiry ? undefined : timeframe.toISOString(),
        indexes
      });

      onClose();
    } finally {
      setLoading(false);
    }
  }, [query, destination, noExpiry, timeframe, indexes, onSubmit, onClose]);

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
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t('page.cases.rules.query')}
            </Typography>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, flex: 1 }}>
                <Card
                  variant="outlined"
                  sx={theme => ({
                    width: '100%',
                    height: theme.spacing(5),
                    p: 1,
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
                </Card>
              </Box>
              <Tooltip title={t('route.search')}>
                <span>
                  <IconButton id="rule-search-button" onClick={handleSearch} disabled={searching || !query.trim()}>
                    <Search />
                  </IconButton>
                </span>
              </Tooltip>
            </Stack>
            {response ? (
              <QueryResultText count={response.total} query={query} />
            ) : (
              <Typography
                sx={theme => ({
                  color: theme.palette.text.secondary,
                  fontSize: '0.9em',
                  fontStyle: 'italic',
                  mt: 0.5
                })}
                variant="body2"
              >
                {t('hit.search.prompt')}
              </Typography>
            )}
          </Box>

          <TextField
            id="rule-destination-input"
            label={t('page.cases.rules.destination')}
            value={destination}
            onChange={e => setDestination(e.target.value)}
            fullWidth
            placeholder="alerts/{{howler.analytic}}"
            helperText={t('page.cases.rules.destination.help')}
            size="small"
          />

          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t('page.cases.rules.indexes')}
            </Typography>
            <FormGroup row>
              <FormControlLabel
                control={
                  <Checkbox
                    id="rule-index-hit"
                    checked={indexes.includes('hit')}
                    onChange={(_e, checked) => {
                      setIndexes(prev => {
                        if (checked) {
                          return prev.includes('hit') ? prev : [...prev, 'hit'];
                        }
                        return prev.filter(i => i !== 'hit');
                      });
                    }}
                  />
                }
                label={t('hit.search.index.hit')}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    id="rule-index-observable"
                    checked={indexes.includes('observable')}
                    onChange={(_e, checked) => {
                      setIndexes(prev => {
                        if (checked) {
                          return prev.includes('observable') ? prev : [...prev, 'observable'];
                        }
                        return prev.filter(i => i !== 'observable');
                      });
                    }}
                  />
                }
                label={t('hit.search.index.observable')}
              />
            </FormGroup>
          </Box>

          <Stack direction="row" spacing={2} alignItems="center">
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DateTimePicker
                slotProps={{
                  textField: {
                    id: 'rule-timeframe-input',
                    fullWidth: true,
                    size: 'small'
                  }
                }}
                label={t('page.cases.rules.timeframe')}
                value={timeframe}
                onChange={nv => {
                  if (nv) {
                    setTimeframe(nv);
                  }
                }}
                disabled={noExpiry}
                ampm={false}
                disablePast
                sx={{ flex: 1 }}
              />
            </LocalizationProvider>
            <FormControlLabel
              control={
                <Checkbox
                  id="rule-no-expiry-checkbox"
                  checked={noExpiry}
                  onChange={(_e, checked) => setNoExpiry(checked)}
                />
              }
              label={t('page.cases.rules.no_expiry')}
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

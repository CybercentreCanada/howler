import { useMonaco } from '@monaco-editor/react';
import { Height, Search } from '@mui/icons-material';
import { Badge, Box, Card, Skeleton, Tooltip, alpha, useTheme } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import TuiIconButton from 'components/elements/addons/buttons/CustomIconButton';
import QueryEditor from 'components/routes/advanced/QueryEditor';
import type { IDisposable, editor } from 'monaco-editor';

import HistoryIcon from '@mui/icons-material/History';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import type { FC } from 'react';
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { sanitizeMultilineLucene } from 'utils/stringUtils';

const DEFAULT_MULTILINE_HEIGHT = 250;
const PROMPT_CONTEXT =
  'isHitQuery && !suggestWidgetVisible && !renameInputVisible && !inSnippetMode && !quickFixWidgetVisible';

export type HitQueryProps = {
  triggerSearch: (query: string) => void;
  onChange?: (query: string, isDirty: boolean) => void;
  searching?: boolean;
  disabled?: boolean;
  compact?: boolean;
};

const HitQuery: FC<HitQueryProps> = ({
  searching = false,
  disabled = false,
  compact = false,
  triggerSearch,
  onChange
}) => {
  const { t } = useTranslation();
  const location = useLocation();
  const theme = useTheme();
  const monaco = useMonaco();

  const savedQuery = useContextSelector(ParameterContext, ctx => ctx.query || 'howler.id:*');

  const prevQuery = useRef<string | null>(null);

  const [query, setQuery] = useState(new URLSearchParams(window.location.search).get('query') || 'howler.id:*');
  const fzfSearch = useContextSelector(HitSearchContext, ctx => ctx?.fzfSearch ?? false);
  const [loaded, setLoaded] = useState(false);
  const [multiline, setMultiline] = useState(false);
  const [y, setY] = useState(0);

  const wrapper = useRef<HTMLDivElement>();

  const search = useCallback(() => triggerSearch(sanitizeMultilineLucene(query)), [query, triggerSearch]);

  const isDirty = useMemo(() => query !== savedQuery, [query, savedQuery]);

  useEffect(() => {
    onChange?.(query, isDirty);
  }, [isDirty, onChange, query]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    const executeDisposable = monaco.editor.addEditorAction({
      id: 'execute-query',
      label: t('route.advanced.execute.query'),
      contextMenuGroupId: 'howler',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: search
    });

    return () => {
      executeDisposable.dispose();
    };
  }, [monaco, t, search]);

  useEffect(() => {
    if (!monaco) {
      return;
    }

    let disposable: IDisposable;
    if (!multiline) {
      disposable = monaco.editor.addKeybindingRule({
        command: 'execute-query',
        keybinding: monaco.KeyCode.Enter,
        when: PROMPT_CONTEXT
      });
    } else {
      disposable = monaco.editor.addKeybindingRule({
        command: null,
        keybinding: monaco.KeyCode.Enter,
        when: PROMPT_CONTEXT
      });
    }

    return () => {
      disposable.dispose();
    };
  }, [monaco, multiline, search]);

  const onMouseMove = useCallback((event: MouseEvent) => {
    const wrapperRect = wrapper.current?.getBoundingClientRect();

    const offset = event.clientY - (wrapperRect.top + DEFAULT_MULTILINE_HEIGHT);

    setY(offset);
  }, []);

  useEffect(() => {
    if (savedQuery && savedQuery !== prevQuery.current) {
      prevQuery.current = savedQuery;
      setQuery(prevQuery.current);
    }
  }, [savedQuery]);

  const onMouseUp = useCallback(() => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }, [onMouseMove]);

  const onMouseDown = useCallback(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  }, [onMouseMove, onMouseUp]);

  const onMount = useCallback((ed: editor.IStandaloneCodeEditor) => {
    ed.createContextKey('isHitQuery', true);
    setLoaded(true);
  }, []);

  const options: editor.IStandaloneEditorConstructionOptions = useMemo(
    () => ({
      fontSize: 17,
      lineHeight: 19,
      lineNumbers: multiline ? 'on' : 'off',
      lineDecorationsWidth: multiline ? 8 : 0,
      lineNumbersMinChars: multiline ? 2 : 0,
      showFoldingControls: 'never',
      scrollBeyondLastLine: !multiline,
      glyphMargin: !multiline,
      renderLineHighlight: multiline ? 'gutter' : 'none',
      overviewRulerLanes: multiline ? 1 : 0
    }),
    [multiline]
  );

  const preppedQuery = useMemo(() => (multiline ? query : query.replaceAll('\n', ' ')), [multiline, query]);

  return (
    <Card
      ref={wrapper}
      variant="outlined"
      sx={[
        {
          width: '100%',
          height: multiline ? `${DEFAULT_MULTILINE_HEIGHT + y}px` : theme.spacing(7),
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
        },
        isDirty &&
          new URLSearchParams(location.search).has('query') && {
            borderColor: 'warning.main'
          },
        compact && {
          p: 0.5,
          height: multiline ? `${DEFAULT_MULTILINE_HEIGHT + y}px` : theme.spacing(5)
        }
      ]}
      onKeyDown={e => e.stopPropagation()}
    >
      <TuiIconButton
        disabled={query.includes('\n#') || disabled}
        sx={{ mr: 1, alignSelf: 'start' }}
        onClick={() => setMultiline(!multiline)}
        color={multiline ? 'primary' : theme.palette.text.primary}
        transparent={!multiline}
        size={compact ? 'small' : 'medium'}
      >
        <Height sx={{ fontSize: '20px' }} />
      </TuiIconButton>
      <QueryEditor
        query={preppedQuery}
        setQuery={setQuery}
        language="lucene"
        height={multiline ? '100%' : '20px'}
        onMount={onMount}
        editorOptions={options}
      />
      {fzfSearch && (
        <Tooltip title={t('route.history')}>
          <HistoryIcon />
        </Tooltip>
      )}
      <TuiIconButton
        disabled={searching || disabled}
        onClick={search}
        sx={{ ml: 1, alignSelf: 'start', flexShrink: 0 }}
        size={compact ? 'small' : 'medium'}
      >
        <Tooltip title={t('route.search')}>
          <Badge invisible={!isDirty} color="warning" variant="dot">
            <Search sx={{ fontSize: '20px' }} />
          </Badge>
        </Tooltip>
      </TuiIconButton>
      {!loaded && (
        <Skeleton
          variant="rectangular"
          sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
          height="100%"
        />
      )}
      {multiline && (
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            height: '10px',
            backgroundColor: theme.palette.divider,
            cursor: 'row-resize',
            zIndex: 1000
          }}
          onMouseDown={onMouseDown}
        />
      )}
      {disabled && (
        <Box
          sx={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            top: 0,
            backgroundColor: alpha(theme.palette.background.paper, 0.65),
            zIndex: 1000
          }}
          onMouseDown={onMouseDown}
        />
      )}
    </Card>
  );
};

export default memo(HitQuery);

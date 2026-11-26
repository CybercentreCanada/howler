import { AutoAwesome, Stop } from '@mui/icons-material';
import { Button, LinearProgress, Popover, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import TuiIconButton from 'components/elements/addons/buttons/CustomIconButton';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Dispatch, FC, KeyboardEvent, SetStateAction } from 'react';
import { memo, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

export type AiQueryButtonProps = {
  query: string;
  setQuery: Dispatch<SetStateAction<string>>;
  disabled?: boolean;
  size?: 'small' | 'medium';
};

const AiQueryButton: FC<AiQueryButtonProps> = ({ query, setQuery, disabled = false, size = 'medium' }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { showErrorMessage, showWarningMessage } = useMySnackbar();

  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => () => controller.current?.abort(), []);

  const generate = useCallback(async () => {
    if (!prompt.trim() || generating) {
      return;
    }

    const original = query;
    const abort = new AbortController();
    controller.current = abort;

    setAnchorEl(null);
    setGenerating(true);
    setStatus('');
    setQuery('');

    try {
      const result = await api.v2.ai.lucene.post(
        { prompt: prompt.trim(), query: original },
        { onText: setQuery, onStatus: setStatus, signal: abort.signal }
      );
      setQuery(result.query);
      if (result.warning) {
        showWarningMessage(result.warning);
      }
    } catch (error) {
      setQuery(original);
      if (!abort.signal.aborted) {
        showErrorMessage((error as Error).message);
      }
    } finally {
      controller.current = null;
      setGenerating(false);
      setStatus('');
    }
  }, [generating, prompt, query, setQuery, showErrorMessage, showWarningMessage]);

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        void generate();
      }
    },
    [generate]
  );

  const features: Record<string, boolean> = config?.configuration?.features ?? {};
  if (!features.ai_lucene) {
    return null;
  }

  return (
    <>
      <TuiIconButton
        id="ai-query-button"
        disabled={disabled && !generating}
        tooltip={generating ? status || t('hit.search.ai.stop') : t('hit.search.ai.button')}
        onClick={event => (generating ? controller.current?.abort() : setAnchorEl(event.currentTarget))}
        color={generating ? 'error' : 'primary'}
        progress={generating}
        clickableWithProgress
        transparent
        sx={{ ml: 1, alignSelf: 'start', flexShrink: 0 }}
        size={size}
      >
        {generating ? <Stop sx={{ fontSize: '20px' }} /> : <AutoAwesome sx={{ fontSize: '20px' }} />}
      </TuiIconButton>
      {generating && (
        <LinearProgress
          id="ai-query-progress"
          sx={theme => ({
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            borderBottomLeftRadius: theme.shape.borderRadius,
            borderBottomRightRadius: theme.shape.borderRadius
          })}
        />
      )}
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ transition: { onEntered: () => input.current?.focus() } }}
      >
        <Stack spacing={1} sx={{ p: 2, width: 420, maxWidth: '90vw' }}>
          <TextField
            id="ai-query-prompt"
            label={t('hit.search.ai.prompt')}
            placeholder={t('hit.search.ai.placeholder')}
            value={prompt}
            onChange={event => setPrompt(event.target.value)}
            onKeyDown={onKeyDown}
            inputRef={input}
            multiline
            minRows={2}
            maxRows={6}
            fullWidth
            size="small"
          />
          <Typography variant="caption" color="text.secondary">
            {t('hit.search.ai.help')}
          </Typography>
          <Button
            id="ai-query-generate"
            variant="contained"
            startIcon={<AutoAwesome />}
            disabled={!prompt.trim()}
            onClick={() => void generate()}
            sx={{ alignSelf: 'end' }}
          >
            {t('hit.search.ai.generate')}
          </Button>
        </Stack>
      </Popover>
    </>
  );
};

export default memo(AiQueryButton);

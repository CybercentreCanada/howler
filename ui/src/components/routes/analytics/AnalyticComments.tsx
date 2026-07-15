import { Clear, Send } from '@mui/icons-material';
import { Chip, Divider, IconButton, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import Comment from 'components/elements/Comment';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserList from 'components/hooks/useMyUserList';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useCallback, useEffect, useMemo, useRef, useState, type FC, type KeyboardEventHandler } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { compareTimestamp } from 'utils/utils';

const MAX_LENGTH = 5000;

const AnalyticComments: FC<{ analytic: Analytic; setAnalytic: (a: Analytic) => void }> = ({
  analytic,
  setAnalytic
}) => {
  const { user } = useAppUser();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const users = useMyUserList(userIds);
  const [searchParams] = useSearchParams();

  const [length, setLength] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showClear, setShowClear] = useState(false);
  const input = useRef<HTMLTextAreaElement>();

  const onSubmit = useCallback(async () => {
    if (!input.current?.value || !analytic || input.current.value.length > MAX_LENGTH) return;

    setLoading(true);
    try {
      const result = await dispatchApi(
        api.analytic.comments.post(analytic.analytic_id, input.current.value, searchParams.get('filter')),
        {
          showError: true,
          throwError: true,
          logError: false
        }
      );

      setAnalytic(result);

      input.current.value = '';
      setShowClear(false);
    } finally {
      setLoading(false);
    }
  }, [analytic, dispatchApi, searchParams, setAnalytic]);

  const onClear = useCallback(() => {
    input.current.value = '';
    setShowClear(false);
    setLength(0);
  }, []);

  const checkForSubmit: KeyboardEventHandler<HTMLDivElement> = useCallback(
    e => {
      e.stopPropagation();

      if (input.current?.value) {
        setShowClear(true);
      }

      if (e.ctrlKey && e.key === 'Enter' && !loading) {
        onSubmit();
      }
    },
    [loading, onSubmit]
  );

  const checkLength = useCallback(() => setLength(input.current?.value.length), []);

  const handleDelete = useCallback(
    async (commentId: string) => {
      await dispatchApi(api.analytic.comments.del(analytic?.analytic_id, [commentId]));

      setAnalytic({
        ...analytic,
        comment: analytic.comment.filter(c => c.id !== commentId)
      });
    },
    [analytic, dispatchApi, setAnalytic]
  );

  const handleEdit = useCallback(
    async (commentId: string, editValue: string) => {
      await dispatchApi(api.analytic.comments.put(analytic?.analytic_id, commentId, editValue));

      setAnalytic({
        ...analytic,
        comment: analytic.comment.map(cmt => (cmt.id !== commentId ? cmt : { ...cmt, value: editValue }))
      });
    },
    [analytic, dispatchApi, setAnalytic]
  );

  const handleQuote = useCallback((value: string) => {
    if (input.current) {
      input.current.value = `${input.current.value.trimStart()}\n\n${value
        .split('\n')
        .map(l => '> ' + l)
        .join('\n')}\n\n`.trimStart();

      setTimeout(() => {
        input.current.focus();
        // SPBK-2197 Fix - https://stackoverflow.com/a/10576409
        input.current.selectionStart = input.current.selectionEnd = input.current.value.length;
      }, 10);
    }
  }, []);

  const handleReact = useCallback(
    async (commentId: string, type: string) => {
      if (type) {
        await dispatchApi(api.analytic.comments.react.put(analytic?.analytic_id, commentId, type));

        setAnalytic({
          ...analytic,
          comment: analytic.comment.map(cmt =>
            cmt.id !== commentId ? cmt : { ...cmt, reactions: { ...(cmt?.reactions ?? {}), [user.username]: type } }
          )
        });
      } else {
        await dispatchApi(api.analytic.comments.react.del(analytic?.analytic_id, commentId));

        setAnalytic({
          ...analytic,
          comment: analytic.comment.map(cmt =>
            cmt.id !== commentId
              ? cmt
              : { ...cmt, reactions: { ...(cmt?.reactions ?? {}), [user.username]: undefined } }
          )
        });
      }
    },
    [analytic, dispatchApi, setAnalytic, user.username]
  );

  useEffect(() => {
    setUserIds(new Set(analytic?.comment.map(c => c.user)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analytic?.analytic_id]);

  const comments = useMemo(
    () =>
      analytic?.comment
        .filter(c => !searchParams.get('filter') || c.detection === searchParams.get('filter'))
        .sort((a, b) => compareTimestamp(b.timestamp, a.timestamp))
        .map(c => (
          <Comment
            key={c.id}
            comment={c}
            users={users}
            handleDelete={() => handleDelete(c.id)}
            handleEdit={value => handleEdit(c.id, value)}
            handleReact={type => handleReact(c.id, type)}
            handleQuote={() => handleQuote(c.value)}
            extra={
              !searchParams.get('filter') && (
                <Chip
                  size="small"
                  sx={theme => ({ marginLeft: '0 !important', mr: `${theme.spacing(2)} !important` })}
                  label={c.detection ?? 'Analytic'}
                />
              )
            }
          />
        )),
    [analytic?.comment, searchParams, handleDelete, handleEdit, handleQuote, handleReact, users]
  );

  return (
    <Stack direction="column" py={2} spacing={1}>
      <Divider orientation="horizontal" flexItem />
      <Stack direction="row" spacing={1}>
        <HowlerAvatar userId={user.username} />
        <TextField
          inputProps={{ sx: theme => ({ fontSize: theme.typography.body2.fontSize }) }}
          InputLabelProps={{ shrink: false }}
          placeholder={t(searchParams.get('filter') ? 'comments.add.detection' : 'comments.add.analytic')}
          onKeyDown={checkForSubmit}
          onChangeCapture={checkLength}
          inputRef={input}
          error={length > MAX_LENGTH}
          fullWidth
          multiline
        />
      </Stack>
      <Stack direction="row" alignItems="center">
        <FlexOne />
        {length > 0.9 * MAX_LENGTH && (
          <Typography variant="caption" sx={[{ opacity: 0.7, mr: 1 }, length > MAX_LENGTH && { color: 'error.main' }]}>
            {length}/{MAX_LENGTH}
          </Typography>
        )}
        {showClear && (
          <IconButton size="small" onClick={onClear} disabled={loading}>
            <Clear fontSize="small" />
          </IconButton>
        )}
        <IconButton size="small" onClick={onSubmit} disabled={loading || length > MAX_LENGTH}>
          <Send fontSize="small" />
        </IconButton>
      </Stack>

      {comments}
    </Stack>
  );
};

export default AnalyticComments;

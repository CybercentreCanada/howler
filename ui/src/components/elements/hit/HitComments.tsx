import { Clear, KeyboardArrowDown, Send } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  AvatarGroup,
  Chip,
  IconButton,
  Skeleton,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import useMatchers from 'components/app/hooks/useMatchers';
import { SocketContext, type RecievedDataType } from 'components/app/providers/SocketProvider';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import useMyApi from 'components/hooks/useMyApi';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Comment as AnalyticComment } from 'models/entities/generated/Comment';
import type { Hit } from 'models/entities/generated/Hit';
import type { SocketEvent } from 'models/socket/HitUpdate';
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
import { useNavigate } from 'react-router-dom';
import { compareTimestamp, sortByTimestamp } from 'utils/utils';
import Comment from '../Comment';
import HowlerAvatar from '../display/HowlerAvatar';
import TypingIndicator from '../display/TypingIndicator';

const MAX_LENGTH = 5000;

interface HitCommentsProps {
  hit: Hit;
  users: { [id: string]: HowlerUser };
}

const HitComments: FC<HitCommentsProps> = ({ hit, users }) => {
  const { user } = useAppUser();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { dispatchApi } = useMyApi();
  const { addListener, removeListener, emit } = useContext(SocketContext);
  const { getMatchingAnalytic } = useMatchers();

  const [typers, setTypers] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showClear, setShowClear] = useState(false);
  const [length, setLength] = useState(0);
  const [analyticId, setAnalyticId] = useState<string>();
  const [analyticComments, setAnalyticComments] = useState<AnalyticComment[]>([]);
  const [comments, setComments] = useState(sortByTimestamp(hit?.howler?.comment));

  const input = useRef<HTMLTextAreaElement>();

  /**
   * Set the list of typers based on updates from the websocket
   */
  const handler = useMemo(
    () => (data: RecievedDataType<SocketEvent>) => {
      // Ensure the action is a user typing, that it's not us, and that were aren't aware of their typing already
      if (
        data.event?.action === 'typing' &&
        data.event?.username !== user.username &&
        !typers.includes(data.event?.username)
      ) {
        setTypers([...typers, data.event.username]);
      } else if (data.event?.action === 'stop_typing' && data.event?.username !== user.username) {
        setTypers(typers.filter(typer => typer !== data.event.username));
      }
    },
    [typers, user.username]
  );

  useEffect(() => {
    addListener<SocketEvent>('hitComments', handler);

    return () => removeListener('hitComments');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handler]);

  useEffect(() => {
    if (hit?.howler?.analytic) {
      getMatchingAnalytic(hit).then(analytic => {
        setAnalyticId(analytic?.analytic_id);
        setAnalyticComments(sortByTimestamp(analytic?.comment ?? []));
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getMatchingAnalytic, hit?.howler?.analytic]);

  const onSubmit = useCallback(async () => {
    if (!input.current?.value || !hit || input.current.value.length > MAX_LENGTH) return;

    setLoading(true);
    try {
      const result = await dispatchApi(api.hit.comments.post(hit.howler.id, input.current.value), {
        showError: true,
        throwError: true,
        logError: false
      });
      setComments(sortByTimestamp(result.howler.comment));

      input.current.value = '';
      setShowClear(false);
    } finally {
      setLoading(false);
    }
  }, [dispatchApi, hit]);

  /**
   * Emit a typing event when textbox is focused
   */
  const onFocus = useCallback(
    () =>
      emit({
        broadcast: true,
        action: 'typing',
        id: hit?.howler?.id
      }),
    [emit, hit?.howler?.id]
  );

  /**
   * Emit a stop typing event when textbox is blurred
   */
  const onBlur = useCallback(
    () =>
      emit({
        broadcast: true,
        action: 'stop_typing',
        id: hit?.howler?.id
      }),
    [emit, hit?.howler?.id]
  );

  const onClear = useCallback(() => {
    input.current.value = '';
    setShowClear(false);
  }, []);

  const checkForSubmit: KeyboardEventHandler<HTMLDivElement> = useCallback(
    e => {
      e.stopPropagation();

      if (input.current?.value) {
        setShowClear(true);
        setLength(input.current.value.length);
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
      await dispatchApi(api.hit.comments.del(hit.howler.id, [commentId]), { throwError: true, showError: true });
      setComments(comments.filter(cmt => cmt.id !== commentId));
    },
    [comments, dispatchApi, hit?.howler?.id]
  );

  const handleEdit = useCallback(
    async (commentId: string, editValue: string) => {
      await dispatchApi(api.hit.comments.put(hit.howler.id, commentId, editValue), {
        throwError: true,
        showError: true
      });
      setComments(comments.map(cmt => (cmt.id !== commentId ? cmt : { ...cmt, value: editValue })));
    },
    [comments, dispatchApi, hit?.howler?.id]
  );

  const handleQuote = useCallback((value: string) => {
    if (input.current) {
      // We use trimStart here so there isn't a bunch of newlines at the beginning of the comment
      // when input.current.value is empty
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
        await dispatchApi(api.hit.comments.react.put(hit.howler.id, commentId, type));

        setComments(
          comments.map(cmt =>
            cmt.id !== commentId ? cmt : { ...cmt, reactions: { ...(cmt?.reactions ?? {}), [user.username]: type } }
          )
        );
      } else {
        await dispatchApi(api.hit.comments.react.del(hit.howler.id, commentId));

        setComments(
          comments.map(cmt =>
            cmt.id !== commentId
              ? cmt
              : { ...cmt, reactions: { ...(cmt?.reactions ?? {}), [user.username]: undefined } }
          )
        );
      }
    },
    [comments, dispatchApi, hit?.howler.id, user.username]
  );

  /**
   * Handle loading the comments when the hit changes
   */
  useEffect(() => {
    if (hit?.howler?.comment) {
      setComments(hit?.howler?.comment.slice().sort((a, b) => compareTimestamp(b.timestamp, a.timestamp)));
    } else if (!hit) {
      setComments([]);
    }
  }, [hit]);

  /**
   * This is the comments for the analytic associated with the hit. We show this at the start of the comment
   * list, as if they've been pinned
   */
  const renderedAnalyticComments = useMemo(() => {
    if (analyticComments.length < 1) {
      return null;
    }

    const displayedComments = analyticComments.filter(c => !c.detection || c.detection === hit?.howler.detection);

    return (
      <Accordion variant="outlined">
        <AccordionSummary expandIcon={<KeyboardArrowDown fontSize="small" />}>
          <Typography variant="body1">{t('comments.analytic', { count: displayedComments.length })}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1}>
            {displayedComments.map(c => (
              <Comment
                key={c.id}
                comment={c}
                extra={
                  <Chip
                    size="small"
                    variant="outlined"
                    onClick={() =>
                      navigate(
                        '/analytics' +
                          (analyticId
                            ? `/${analyticId}?tab=comments` + (c.detection ? `&filter=${c.detection}` : '')
                            : '')
                      )
                    }
                    sx={theme => ({ marginLeft: '0 !important', mr: `${theme.spacing(2)} !important` })}
                    label={`${hit?.howler?.analytic ?? 'Analytic'}${c.detection ? ' - ' + c.detection : ''}`}
                  />
                }
                users={users}
              />
            ))}
          </Stack>
        </AccordionDetails>
      </Accordion>
    );
  }, [analyticComments, analyticId, hit?.howler.analytic, hit?.howler.detection, navigate, t, users]);

  const renderedComments = useMemo(
    () =>
      comments.map(c => (
        <Comment
          key={c.id}
          comment={c}
          users={users}
          handleDelete={() => handleDelete(c.id)}
          handleEdit={value => handleEdit(c.id, value)}
          handleReact={type => handleReact(c.id, type)}
          handleQuote={() => handleQuote(c.value)}
        />
      )),
    [comments, handleDelete, handleEdit, handleQuote, handleReact, users]
  );

  return (
    <Stack sx={{ py: 1, pr: 1 }} spacing={1}>
      {hit && renderedAnalyticComments}
      <Stack direction="row" spacing={1}>
        <HowlerAvatar userId={user.username} />
        <TextField
          inputProps={{ sx: theme => ({ fontSize: theme.typography.body2.fontSize }) }}
          InputLabelProps={{ shrink: false }}
          placeholder={t('comments.add')}
          onKeyDown={checkForSubmit}
          onChangeCapture={checkLength}
          inputRef={input}
          onFocus={onFocus}
          onBlur={onBlur}
          error={length > MAX_LENGTH}
          fullWidth
          multiline
        />
      </Stack>
      <Stack direction="row" alignItems="center">
        {typers.length > 0 && (
          <>
            <AvatarGroup componentsProps={{ additionalAvatar: { sx: { height: 24, width: 24, fontSize: '12px' } } }}>
              {typers.map(typer => (
                <HowlerAvatar key={typer} userId={typer} sx={{ height: 24, width: 24 }} />
              ))}
            </AvatarGroup>
            <TypingIndicator />
          </>
        )}
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
      {hit ? (
        renderedComments
      ) : (
        <>
          <Stack direction="row" spacing={1}>
            <Skeleton width={40} height={40} variant="circular"></Skeleton>
            <Skeleton width="100%" height={80} variant="rounded"></Skeleton>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Skeleton width={40} height={40} variant="circular"></Skeleton>
            <Skeleton width="100%" height={100} variant="rounded"></Skeleton>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Skeleton width={40} height={40} variant="circular"></Skeleton>
            <Skeleton width="100%" height={80} variant="rounded"></Skeleton>
          </Stack>
        </>
      )}
    </Stack>
  );
};

export default HitComments;

import {
  Celebration,
  Check,
  Clear,
  Delete,
  Edit,
  Favorite,
  FireTruck,
  FormatQuote,
  Mood,
  RocketLaunch,
  ThumbDown,
  ThumbUp
} from '@mui/icons-material';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import {
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Fade,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
  type Theme
} from '@mui/material';
import { useAppUser } from 'commons/components/app/hooks';
import FlexOne from 'components/elements/addons/layout/FlexOne';
import useMyUtils from 'components/hooks/useMyUtils';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { AnalyticComment } from 'models/entities/generated/AnalyticComment';
import type { Comment as HowlerComment } from 'models/entities/generated/Comment';
import type { FC, KeyboardEventHandler, ReactNode } from 'react';
import { memo, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { compareTimestamp, twitterShort } from 'utils/utils';
import HowlerAvatar from './display/HowlerAvatar';
import HowlerCard from './display/HowlerCard';
import Markdown from './display/Markdown';

const REACTION_ICONS = {
  '+1': ThumbUp,
  '-1': ThumbDown,
  laugh: Mood,
  confetti: Celebration,
  heart: Favorite,
  rocket: RocketLaunch,
  fire: FireTruck
};

const Comment: FC<{
  comment: HowlerComment | AnalyticComment;
  handleDelete?: () => Promise<void>;
  handleEdit?: (value: string) => Promise<void>;
  handleReact?: (type: string) => Promise<void>;
  handleQuote?: () => void;
  onClick?: () => void;
  users: { [id: string]: HowlerUser };
  extra?: ReactNode;
}> = ({ comment, handleDelete, handleEdit, handleQuote, handleReact, users, extra, onClick }) => {
  const { t } = useTranslation();
  const { user } = useAppUser();
  const { shiftColor } = useMyUtils();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [wasEdited, setEdited] = useState(compareTimestamp(comment.modified, comment.timestamp) > 1);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showInteractions, setShowInteractions] = useState(false);
  const [editValue, setEditValue] = useState(comment.value);

  const handleOpen = useCallback((event: React.MouseEvent<HTMLButtonElement>) => setAnchorEl(event.currentTarget), []);
  const handleClose = useCallback(() => setAnchorEl(null), []);

  const onDelete = useCallback(async () => {
    setLoading(true);
    try {
      await handleDelete();
    } finally {
      setLoading(false);
      handleClose();
    }
  }, [handleDelete, handleClose]);

  const onEdit = useCallback(async () => {
    if (editValue === comment.value) {
      setEditing(false);
      return;
    }

    try {
      setLoading(true);
      await handleEdit(editValue);
      setEdited(true);
    } finally {
      setLoading(false);
      setEditing(false);
    }
  }, [comment.value, editValue, handleEdit]);

  const checkForActions: KeyboardEventHandler<HTMLDivElement> = useCallback(
    e => {
      e.stopPropagation();

      if (e.ctrlKey && e.key === 'Enter' && !loading) {
        onEdit();
      } else if (e.key === 'Escape') {
        setEditing(false);
      }
    },
    [loading, onEdit]
  );

  const onQuote = useCallback(() => {
    handleQuote();
    handleClose();
  }, [handleClose, handleQuote]);

  const reactions = useMemo(() => {
    return Object.keys(REACTION_ICONS).map(type => {
      const quantity = Object.values(comment?.reactions ?? {}).filter(r => r === type).length;
      const Icon = REACTION_ICONS[type];

      return !!quantity || (showInteractions && handleReact) ? (
        <Fade key={type} in>
          <Chip
            size="small"
            variant="outlined"
            color={comment.reactions?.[user.username] === type ? 'primary' : 'default'}
            icon={<Icon />}
            onClick={handleReact ? () => handleReact(comment.reactions?.[user.username] !== type ? type : null) : null}
            sx={[
              !quantity && {
                '& svg': { mr: '-14px !important' }
              }
            ]}
            label={quantity || null}
          />
        </Fade>
      ) : null;
    });
  }, [comment.reactions, handleReact, showInteractions, user.username]);

  return (
    <Stack direction="row" spacing={1} key={comment.id}>
      <HowlerAvatar userId={comment.user} />
      <HowlerCard
        key={comment.timestamp}
        onClick={onClick}
        onMouseEnter={() => setShowInteractions(true)}
        onMouseLeave={() => setShowInteractions(false)}
        sx={[
          { p: 2, pb: 0, pt: 1, border: 'thin solid transparent' },
          editing && { flex: 1 },
          onClick && { '&:hover': { cursor: 'pointer', borderColor: 'primary.main' } }
        ]}
      >
        <CardContent sx={{ p: 0 }}>
          <Stack direction="row" alignItems="center" spacing={2}>
            <Typography variant="body1">{users[comment.user]?.name ?? comment.user}</Typography>
            {wasEdited && (
              <Typography
                variant="caption"
                sx={theme => ({
                  marginRight: `${theme.spacing(1)} !important`,
                  color: shiftColor(theme.palette.text.primary, 0.25)
                })}
              >
                {t('comments.edited')}
              </Typography>
            )}
            <Tooltip title={new Date(comment.timestamp).toLocaleString()}>
              <Typography
                variant="caption"
                sx={theme => ({
                  marginRight: `${theme.spacing(1)} !important`,
                  color: shiftColor(theme.palette.text.primary, 0.25)
                })}
              >
                {twitterShort(comment.timestamp)}
              </Typography>
            </Tooltip>
            {extra}
            {(handleDelete || handleEdit || handleQuote) && (
              <Fade in={showInteractions}>
                <IconButton
                  size="small"
                  sx={[{ marginLeft: 'auto !important' }, editing && { display: 'none' }]}
                  id={`comment${comment.id}-button`}
                  aria-haspopup="true"
                  aria-controls={anchorEl ? `comment${comment.id}-action-menu` : undefined}
                  aria-expanded={anchorEl ? 'true' : undefined}
                  onClick={handleOpen}
                >
                  <MoreHorizIcon fontSize="small" />
                </IconButton>
              </Fade>
            )}
            <Menu
              id={`comment${comment.id}-action-menu`}
              anchorEl={anchorEl}
              open={!!anchorEl}
              onClose={handleClose}
              MenuListProps={{
                dense: true,
                'aria-labelledby': `comment${comment.id}-button`
              }}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right'
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'right'
              }}
            >
              {handleDelete && (comment?.user === user.username || user.is_admin) && (
                <MenuItem onClick={onDelete} disabled={loading}>
                  <ListItemIcon>
                    {loading ? (
                      <CircularProgress size={18} sx={theme => ({ color: theme.palette.text.primary })} />
                    ) : (
                      <Delete />
                    )}
                  </ListItemIcon>
                  <ListItemText>{t('comments.delete')}</ListItemText>
                </MenuItem>
              )}
              {handleEdit && comment?.user === user.username && (
                <MenuItem
                  onClick={() => {
                    setEditing(!editing);
                    handleClose();
                  }}
                  disabled={loading}
                >
                  <ListItemIcon>
                    <Edit />
                  </ListItemIcon>
                  <ListItemText>{!editing ? t('comments.edit') : t('comments.edit.stop')}</ListItemText>
                </MenuItem>
              )}
              {handleQuote && (
                <MenuItem onClick={onQuote} disabled={loading}>
                  <ListItemIcon>
                    <FormatQuote />
                  </ListItemIcon>
                  <ListItemText>{t('comments.quote')}</ListItemText>
                </MenuItem>
              )}
            </Menu>
          </Stack>
          {!editing ? (
            <Typography
              variant="body2"
              color="text.secondary"
              component="div"
              sx={{
                '& > *': {
                  wordBreak: 'break-word'
                },
                '& > :last-child': {
                  marginBottom: 0
                }
              }}
            >
              <Markdown md={comment.value} />
            </Typography>
          ) : (
            <TextField
              sx={{ mt: 1 }}
              inputProps={{ sx: (theme: Theme) => ({ fontSize: theme.typography.body2.fontSize }) }}
              inputRef={(ref: React.RefObject<HTMLInputElement>) => setTimeout(() => ref?.current?.focus(), 100)}
              defaultValue={comment.value}
              onChange={e => setEditValue(e.target.value)}
              onKeyDown={checkForActions}
              fullWidth
              multiline
            />
          )}
        </CardContent>
        <CardActions sx={{ px: 0 }}>
          <Collapse
            in={editing || showInteractions || Object.values(comment?.reactions ?? {}).length > 0}
            sx={{ width: '100%' }}
          >
            <Stack direction="row" sx={{ width: '100%' }} spacing={0.5}>
              {reactions}
              <FlexOne />
              {editing && (
                <>
                  <IconButton size="small" onClick={() => setEditing(false)} disabled={loading}>
                    <Clear fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={onEdit} disabled={loading}>
                    <Check fontSize="small" />
                  </IconButton>
                </>
              )}
            </Stack>
          </Collapse>
        </CardActions>
      </HowlerCard>
    </Stack>
  );
};

export default memo(Comment);

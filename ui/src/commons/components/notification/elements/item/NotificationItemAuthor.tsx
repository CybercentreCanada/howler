import { Link, Typography, useTheme } from '@mui/material';
import type { FeedAuthor } from 'commons/components/notification/FeedModels';

import { memo, useMemo, type FC } from 'react';

export const NotificationItemAuthor: FC<{ author: FeedAuthor }> = memo(({ author = null }) => {
  const theme = useTheme();

  //Limit github avatar size to 50px
  const avatar = useMemo<string>(() => {
    if (author?.avatar.includes('github')) {
      let url = new URLSearchParams(author?.avatar);
      url.append('s', '50');
      return decodeURIComponent(url.toString());
    } else {
      return author?.avatar;
    }
  }, [author]);

  const NotificationAuthorContent = useMemo(
    () => (
      <>
        {avatar && (
          <img
            src={avatar}
            alt={avatar}
            style={{
              maxHeight: '25px',
              borderRadius: '50%',
              color: theme.palette.text.secondary,
              marginRight: theme.spacing(1)
            }}
          />
        )}
        <Typography
          variant="caption"
          color="textSecondary"
          sx={
            author?.url &&
            author?.url !== '' && {
              color: theme.palette.text.secondary,
              transition: 'color 225ms cubic-bezier(0, 0, 0.2, 1) 0ms',
              '&:hover': {
                color: theme.palette.mode === 'dark' ? theme.palette.secondary.light : theme.palette.secondary.dark
              }
            }
          }
        >
          {author?.name}
        </Typography>
      </>
    ),
    [author?.name, author?.url, avatar, theme]
  );

  return author && author?.url && author?.url !== '' ? (
    <Link
      key={`${author?.name}`}
      title={author?.url}
      href={author?.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{ display: 'contents' }}
    >
      {NotificationAuthorContent}
    </Link>
  ) : (
    <div key={`${author?.name}`} style={{ display: 'contents' }}>
      {NotificationAuthorContent}
    </div>
  );
});

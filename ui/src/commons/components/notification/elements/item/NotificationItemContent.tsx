import { Box, Link, Typography } from '@mui/material';
import { type FeedItem } from 'commons/components/notification';
import DOMPurify from 'dompurify';
import { memo, type FC } from 'react';
import Markdown from 'react-markdown';

export const NotificationItemContent: FC<FeedItem> = memo(
  ({ content_html = null, content_text = null, content_md = null }) =>
    content_md ? (
      <Box sx={{ '& *': { margin: 0, marginBottom: 0.5 }, overflow: 'hidden' }}>
        <Markdown components={{ a: props => <Link href={props.href}>{props.children}</Link> }}>{content_md}</Markdown>
      </Box>
    ) : content_html ? (
      <Typography
        sx={{ '& *': { margin: 0, marginBottom: 0.5 }, overflow: 'hidden' }}
        dangerouslySetInnerHTML={{
          __html: DOMPurify.sanitize(content_html, { USE_PROFILES: { html: true } })
        }}
      />
    ) : content_text ? (
      <Typography
        sx={{ '& *': { margin: 0, marginBottom: 0.5 }, overflow: 'hidden' }}
        variant="body2"
        color="textPrimary"
      >
        {content_text}
      </Typography>
    ) : null
);

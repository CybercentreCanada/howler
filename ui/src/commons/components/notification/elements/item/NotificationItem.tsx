import { useTheme } from '@mui/material';
import { memo, type FC } from 'react';

import { NotificationItemAuthor } from 'commons/components/notification/elements/item/NotificationItemAuthor';
import { NotificationItemContent } from 'commons/components/notification/elements/item/NotificationItemContent';
import { NotificationItemDate } from 'commons/components/notification/elements/item/NotificationItemDate';
import { NotificationItemImage } from 'commons/components/notification/elements/item/NotificationItemImage';
import { NotificationItemTag } from 'commons/components/notification/elements/item/NotificationItemTag';
import { NotificationItemTitle } from 'commons/components/notification/elements/item/NotificationItemTitle';
import type { FeedItem } from 'commons/components/notification/FeedModels';

export const NotificationItem: FC<{ item?: FeedItem }> = memo(({ item = null }) => {
  const theme = useTheme();

  return !item ? null : (
    <div
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start'
      }}
    >
      <NotificationItemDate {...item} />
      <NotificationItemTitle {...item} />
      <NotificationItemContent {...item} />
      <NotificationItemImage {...item} />
      <div
        style={{
          width: '100%',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          marginTop: theme.spacing(1)
        }}
      >
        {item?.tags && item?.tags.map(tag => <NotificationItemTag key={`${tag}`} tag={tag} />)}
        <div style={{ flex: 1 }} />
        {item?.authors &&
          item?.authors.map(author => <NotificationItemAuthor key={`${author?.name}`} author={author} />)}
      </div>
    </div>
  );
});

import { Typography } from '@mui/material';
import { type FeedItem } from 'commons/components/notification';
import moment from 'moment';
import { memo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

export const NotificationItemDate: FC<FeedItem> = memo(({ date_published = null }) => {
  const { i18n } = useTranslation(['notification']);
  return !date_published ? null : (
    <Typography lineHeight="revert" display="block" variant="caption" color="textSecondary">
      <>{moment(date_published).locale(i18n.language).fromNow()}</>
    </Typography>
  );
});

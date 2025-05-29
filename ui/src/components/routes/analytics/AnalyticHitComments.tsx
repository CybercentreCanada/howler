import { Chip, Divider, LinearProgress, Stack } from '@mui/material';
import api from 'api';
import Comment from 'components/elements/Comment';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMyUserList from 'components/hooks/useMyUserList';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Comment as HitComment } from 'models/entities/generated/Comment';
import type { FC } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import { compareTimestamp } from 'utils/utils';

interface CommentData {
  hitId: string;
  detection: string;
  comment: HitComment;
}

const AnalyticHitComments: FC<{ analytic: Analytic }> = ({ analytic }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const pageCount = useMyLocalStorageItem(StorageKey.PAGE_COUNT, 25)[0];

  const [comments, setComments] = useState<CommentData[]>([]);
  const [loading, setLoading] = useState(false);
  const [userIds, setUserIds] = useState<Set<string>>(new Set());

  const users = useMyUserList(userIds);

  useEffect(() => {
    setUserIds(new Set(comments.map(c => c.comment.user)));
  }, [comments]);

  useEffect(() => {
    if (!analytic) {
      return;
    }

    setLoading(true);
    api.search.hit
      .post({
        query: `howler.analytic:${analytic.name} AND _exists_:howler.comment`,
        rows: pageCount
      })
      .then(response => {
        setComments(
          response.items.flatMap(h =>
            h.howler.comment.map(comment => ({
              hitId: h.howler.id,
              detection: h.howler.detection,
              comment
            }))
          )
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [analytic, pageCount]);

  const commentEls = useMemo(
    () =>
      loading ? (
        <LinearProgress />
      ) : (
        comments
          .filter(c => !searchParams.get('filter') || c.detection === searchParams.get('filter'))
          .sort((a, b) => compareTimestamp(b.comment.timestamp, a.comment.timestamp))
          .map(c => (
            <Comment
              key={c.comment.id}
              comment={c.comment}
              users={users}
              onClick={() => navigate(`/hits/${c.hitId}`)}
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
          ))
      ),
    [loading, comments, searchParams, users, navigate]
  );

  return (
    <Stack direction="column" py={2} spacing={1}>
      <Divider orientation="horizontal" flexItem />
      {commentEls}
    </Stack>
  );
};

export default AnalyticHitComments;

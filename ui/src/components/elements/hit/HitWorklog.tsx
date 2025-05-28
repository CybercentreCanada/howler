import { KeyboardArrowUp } from '@mui/icons-material';
import { CardContent, CardHeader, Divider, Skeleton, Stack, Tooltip, Typography, useTheme } from '@mui/material';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import useMyUtils from 'components/hooks/useMyUtils';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Hit } from 'models/entities/generated/Hit';
import type { Log } from 'models/entities/generated/Log';
import type { FC } from 'react';
import { useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import { compareTimestamp, twitterShort } from 'utils/utils';
import HowlerAvatar from '../display/HowlerAvatar';
import HowlerCard from '../display/HowlerCard';
import Markdown from '../display/Markdown';

const HitWorklog: FC<{ hit: Hit; users: { [id: string]: HowlerUser } }> = ({ hit, users }) => {
  const theme = useTheme();
  const { shiftColor } = useMyUtils();
  const { t } = useTranslation();

  // This value tracks the latest hit version we have seen.
  // That way, when we see a new version, we can highlight the new changes in the UI
  const [initialVersions, setInitialVersions] = useMyLocalStorageItem<{ [index: string]: string }>(
    StorageKey.LAST_SEEN,
    {}
  );

  /**
   * The variable that tracks the grouped worklog entries. For the sake of readability, we group together log items that are close in time and created
   * by the same user. We also add a split between previously seen and new worklog entries.
   */
  const worklogGroups = useMemo(
    () => {
      let setInitialVersion = false;

      return (hit?.howler?.log || [])
        .slice()
        .sort((a, b) => compareTimestamp(b.timestamp, a.timestamp))
        .reduce((acc, l) => {
          if (!initialVersions[hit.howler.id] && !setInitialVersion) {
            setInitialVersion = true;
            setInitialVersions({
              ...initialVersions,
              [hit.howler.id]: l.previous_version
            });
          }

          // Initialize the worklog card groups
          if (!acc.length) {
            return [[l]];
          }

          // Get the the most recent worklog card
          const currArr = acc[acc.length - 1];
          if (
            // Does this log version match the saved version?
            l.previous_version === initialVersions[hit.howler.id] &&
            // Does the previous entry not match?
            currArr[currArr.length - 1].previous_version !== initialVersions[hit.howler.id]
          ) {
            // If so, we've figured out where the new logs should start, so we start a new card.
            acc.push([l]);
            return acc;
          }

          // If a different user added this to the log, or enough time has passed, we start a new card
          if (currArr[0].user === l.user && compareTimestamp(currArr[0].timestamp, l.timestamp) < 60 * 5) {
            currArr.push(l);
            return acc;
          }

          acc.push([l]);
          return acc;
        }, [] as Log[][]);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hit?.howler?.log]
  );

  useEffect(() => {
    // On unmount, mark the latest entry version as the last seen version.
    return () => {
      if (hit?.howler.id) {
        setInitialVersions({
          ...initialVersions,
          [hit.howler.id]: worklogGroups[0][0]?.previous_version ?? initialVersions[hit.howler.id]
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // We now render the actual HTML from our grouped worklog items
  const worklogEls = useMemo(() => {
    if (worklogGroups.length > 0) {
      return worklogGroups.flatMap((ls, index) => {
        const result = [];

        if (index > 0 && initialVersions[hit.howler.id] && ls[0].previous_version === initialVersions[hit.howler.id]) {
          result.push(
            <Divider key="new">
              <Stack direction="row">
                <KeyboardArrowUp sx={{ color: 'text.secondary' }} fontSize="small" />
                <Typography variant="caption" color="text.secondary">
                  {t('hit.worklog.new')}
                </Typography>
                <KeyboardArrowUp sx={{ color: 'text.secondary' }} fontSize="small" />
              </Stack>
            </Divider>
          );
        }

        result.push(
          <HowlerCard key={ls[0].timestamp} elevation={4}>
            <CardHeader
              avatar={<HowlerAvatar userId={ls[0].user} />}
              title={users[ls[0].user]?.name ?? ls[0].user}
              subheader={
                <Tooltip title={new Date(ls[0].timestamp).toLocaleString()}>
                  <Typography variant="caption">{twitterShort(ls[0].timestamp)}</Typography>
                </Tooltip>
              }
            />
            <CardContent>
              <Stack spacing={1} divider={<Divider orientation="horizontal" />}>
                {ls.map(l => (
                  <Typography
                    key={l.timestamp}
                    variant="body2"
                    color="text.secondary"
                    component="div"
                    position="relative"
                  >
                    {l.explanation ? (
                      <Markdown md={l.explanation.trim()} />
                    ) : (
                      <>
                        <span>{t('hit.worklog.updated')}&nbsp;</span>
                        <code>{l.key}</code>
                        <span>:&nbsp;</span>
                        {
                          {
                            set: (
                              <span>
                                {l.previous_value} {t('hit.worklog.set')} {l.new_value}
                              </span>
                            ),
                            appended: (
                              <span>
                                {l.new_value} {t('hit.worklog.appended')} {l.previous_value?.replace(/[[\]]/g, '')}
                              </span>
                            ),
                            removed: (
                              <span>
                                {l.new_value} {t('hit.worklog.removed')} {l.previous_value?.replace(/[[\]]/g, '')}
                              </span>
                            )
                          }[l.type]
                        }
                      </>
                    )}
                    {ls.length > 1 && (
                      <Tooltip title={new Date(l.timestamp).toLocaleString()}>
                        <Typography
                          sx={{ ml: 0.5, position: 'absolute', right: '1rem', top: 0 }}
                          variant="caption"
                          color={shiftColor(theme.palette.text.primary, 0.5)}
                        >
                          {twitterShort(l.timestamp)}
                        </Typography>
                      </Tooltip>
                    )}
                  </Typography>
                ))}
              </Stack>
            </CardContent>
          </HowlerCard>
        );

        return result;
      });
    } else if (!hit?.howler) {
      return (
        <>
          <Skeleton width="100%" height={200} variant="rounded" />
          <Skeleton width="100%" height={220} variant="rounded" />
          <Skeleton width="100%" height={150} variant="rounded" />
        </>
      );
    }
  }, [worklogGroups, hit.howler, initialVersions, users, t, shiftColor, theme.palette.text.primary]);

  return (
    <Stack sx={{ p: 2 }} spacing={1}>
      {worklogEls}
    </Stack>
  );
};

export default HitWorklog;

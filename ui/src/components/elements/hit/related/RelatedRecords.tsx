import { Link as LinkIcon } from '@mui/icons-material';
import { alpha, Box, Chip, Divider, Stack, useTheme } from '@mui/material';
import api from 'api';
import CasePreview from 'components/elements/case/CasePreview';
import ChipPopper from 'components/elements/display/ChipPopper';
import ObservablePreview from 'components/elements/observable/ObservablePreview';
import useMyApi from 'components/hooks/useMyApi';
import { uniq } from 'lodash-es';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { WithMetadata } from 'models/WithMetadata';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { isCase, isHit, isObservable } from 'utils/typeUtils';
import HitPreview from '../HitPreview';

const RelatedRecords: FC<{ hit: Hit }> = ({ hit }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [open, setOpen] = useState(false);
  const [records, setRecords] = useState<WithMetadata<Hit | Observable | Case>[]>([]);
  const [filter, setFilter] = useState<string>(null);

  const related = useMemo(() => hit?.howler.related ?? [], [hit?.howler.related]);

  useEffect(() => {
    if (!open) {
      return;
    }

    (async () => {
      const result = await dispatchApi(
        api.v2.search.post<WithMetadata<Hit | Observable | Case>>('hit,observable,case', {
          query: `howler.id:(${related.join(' OR ')}) OR case_id:(${related.join(' OR ')})`
        })
      );

      setRecords(result.items);
    })();
  }, [dispatchApi, open, related]);

  return (
    <ChipPopper
      // eslint-disable-next-line jsx-a11y/anchor-is-valid
      icon={<LinkIcon />}
      label={<span style={{ cursor: 'pointer' }}>{t('hit.header.related', { count: hit.howler.related.length })}</span>}
      slotProps={{
        chip: { disabled: related.length < 1 },
        paper: {
          elevation: 4,
          onAuxClick: ev => ev.stopPropagation()
        }
      }}
      disablePortal={false}
      placement="bottom-end"
      onToggle={_open => setOpen(_open)}
    >
      <Stack direction="row" spacing={1} mb={1} justifyContent="end">
        {uniq(records.map(record => record.__index)).map(_type => (
          <Chip
            color={_type === filter ? 'primary' : 'default'}
            key={_type}
            label={_type}
            onClick={() => setFilter(current => (current === _type ? null : _type))}
          />
        ))}
      </Stack>
      <Stack maxWidth="40vw" maxHeight="70vh" sx={{ overflowY: 'auto' }}>
        <Divider />
        {records
          .filter(record => !filter || record.__index === filter)
          .map(entry => {
            if (isHit(entry)) {
              const key = entry.howler.id;

              return (
                <Box
                  key={key}
                  p={1}
                  position="relative"
                  flex={1}
                  sx={{
                    '& > a': {
                      backgroundColor: 'transparent',
                      transition: theme.transitions.create('background-color', {
                        duration: theme.transitions.duration.shortest
                      }),
                      '&:hover': {
                        backgroundColor: alpha('#555', 0.5)
                      }
                    }
                  }}
                >
                  <Link
                    to={`/hits/${key}`}
                    style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={t('hit.header.view.hit', { id: key })}
                  />
                  <HitPreview hit={entry} />
                </Box>
              );
            } else if (isCase(entry)) {
              const key = entry.case_id;
              return (
                <Box
                  key={key}
                  flex={1}
                  p={1}
                  position="relative"
                  sx={{
                    '& > a': {
                      backgroundColor: 'transparent',
                      transition: theme.transitions.create('background-color', {
                        duration: theme.transitions.duration.shortest
                      }),
                      '&:hover': {
                        backgroundColor: alpha('#555', 0.5)
                      }
                    }
                  }}
                >
                  <Link
                    to={`/cases/${key}`}
                    style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }}
                    target="_blank"
                    aria-label={t('hit.header.view.case', { id: key })}
                  />
                  <CasePreview case={entry} />
                </Box>
              );
            } else if (isObservable(entry)) {
              const key = entry.howler.id;
              return (
                <Box
                  key={key}
                  flex={1}
                  p={1}
                  position="relative"
                  sx={{
                    '& > a': {
                      backgroundColor: 'transparent',
                      transition: theme.transitions.create('background-color', {
                        duration: theme.transitions.duration.shortest
                      }),
                      '&:hover': {
                        backgroundColor: alpha('#555', 0.5)
                      }
                    }
                  }}
                >
                  <Link
                    to={`/observables/${key}`}
                    style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }}
                    target="_blank"
                    aria-label={t('hit.header.view.observable', { id: key })}
                  />
                  <ObservablePreview observable={entry} />
                </Box>
              );
            }
          })}
      </Stack>
    </ChipPopper>
  );
};

export default memo(RelatedRecords);

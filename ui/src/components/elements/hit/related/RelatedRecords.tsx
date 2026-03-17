import { Link as LinkIcon } from '@mui/icons-material';
import { alpha, Box, Chip, Divider, Stack, useTheme } from '@mui/material';
import CasePreview from 'components/elements/case/CasePreview';
import ChipPopper from 'components/elements/display/ChipPopper';
import ObservablePreview from 'components/elements/observable/ObservablePreview';
import useRelatedRecords from 'components/hooks/useRelatedRecords';
import { identity, uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useMemo, useState, type FC, type PropsWithChildren } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { isCase, isHit, isObservable } from 'utils/typeUtils';
import HitPreview from '../HitPreview';

const RecordLink: FC<PropsWithChildren<{ to: string; ariaLabel: string }>> = ({ to, ariaLabel, children }) => {
  const theme = useTheme();
  return (
    <Box
      p={1}
      flex={1}
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
        to={to}
        style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={ariaLabel}
      />
      {children}
    </Box>
  );
};

const RelatedRecords: FC<{ hit: Hit }> = ({ hit }) => {
  const { t } = useTranslation();

  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<string>(null);

  const related = useMemo(() => hit?.howler.related ?? [], [hit?.howler.related]);
  const records = useRelatedRecords(related, open);

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
        {uniq(records.map(record => record.__index))
          .filter(identity)
          .map(_type => (
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
                <RecordLink key={key} to={`/hits/${key}`} ariaLabel={t('hit.header.view.hit', { id: key })}>
                  <HitPreview hit={entry} />
                </RecordLink>
              );
            } else if (isCase(entry)) {
              const key = entry.case_id;
              return (
                <RecordLink key={key} to={`/cases/${key}`} ariaLabel={t('hit.header.view.case', { id: key })}>
                  <CasePreview case={entry} />
                </RecordLink>
              );
            } else if (isObservable(entry)) {
              const key = entry.howler.id;
              return (
                <RecordLink
                  key={key}
                  to={`/observables/${key}`}
                  ariaLabel={t('hit.header.view.observable', { id: key })}
                >
                  <ObservablePreview observable={entry} />
                </RecordLink>
              );
            }
          })}
      </Stack>
    </ChipPopper>
  );
};

export default memo(RelatedRecords);

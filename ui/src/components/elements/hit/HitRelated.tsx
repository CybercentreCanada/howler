import { Box, Stack, Tab, Tabs, useTheme } from '@mui/material';
import ObservableCard from 'components/elements/observable/ObservableCard';
import useRelatedRecords from 'components/hooks/useRelatedRecords';
import { groupBy } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { isCase, isHit, isObservable } from 'utils/typeUtils';
import CaseCard from '../case/CaseCard';
import HitCard from './HitCard';
import { HitLayout } from './HitLayout';
import RelatedLink from './related/RelatedLink';

const HitRelated: FC<{ hit: Hit }> = ({ hit }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const related = useMemo(() => hit?.howler.related ?? [], [hit?.howler.related]);
  const records = useRelatedRecords(related, related.length > 0);

  const groups = groupBy(records, '__index');

  const hasLinks = (hit?.howler.links?.length ?? 0) > 0;
  const tabs = [
    hasLinks && 'links',
    groups.hit?.length > 0 && 'hit',
    groups.case?.length > 0 && 'case',
    groups.observable?.length > 0 && 'observable'
  ].filter(Boolean) as string[];

  const [activeTab, setActiveTab] = useState<string | false>(false);
  const currentTab = activeTab !== false && tabs.includes(activeTab) ? activeTab : (tabs[0] ?? false);

  if (!hit) {
    return null;
  }

  return (
    <Box sx={{ borderTop: `thin solid ${theme.palette.divider}`, height: '100%', flex: 1, mr: 2, pb: 2 }}>
      <Tabs value={currentTab} onChange={(_, v) => setActiveTab(v)} variant="scrollable" scrollButtons="auto">
        {hasLinks && <Tab value="links" label={t('hit.related.tab.links')} />}
        {groups.hit?.length > 0 && <Tab value="hit" label={t('hit.related.tab.hit')} />}
        {groups.case?.length > 0 && <Tab value="case" label={t('hit.related.tab.case')} />}
        {groups.observable?.length > 0 && <Tab value="observable" label={t('hit.related.tab.observable')} />}
      </Tabs>

      {currentTab === 'links' && (
        <Box display="grid" gridTemplateColumns="repeat(auto-fill, minmax(200px, 1fr))" gap={1} pt={1}>
          {hit.howler.links.map(l => (
            <RelatedLink key={l.title + l.href} {...l} />
          ))}
        </Box>
      )}

      {currentTab === 'hit' && (
        <Stack spacing={1} pt={1}>
          {records.filter(isHit).map(h => (
            <Link
              key={h.howler.id}
              to={`/hits/${h.howler.id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              <HitCard id={h.howler.id} layout={HitLayout.NORMAL} />
            </Link>
          ))}
        </Stack>
      )}

      {currentTab === 'case' && (
        <Stack spacing={1} pt={1}>
          {records.filter(isCase).map(c => (
            <Link
              key={c.case_id}
              to={`/cases/${c.case_id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              <CaseCard case={c} />
            </Link>
          ))}
        </Stack>
      )}

      {currentTab === 'observable' && (
        <Stack spacing={1} pt={1}>
          {(records.filter(isObservable) as Observable[]).map(o => (
            <Link
              key={o.howler.id}
              to={`/observables/${o.howler.id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              <ObservableCard observable={o} />
            </Link>
          ))}
        </Stack>
      )}
    </Box>
  );
};

export default HitRelated;

import { CardContent, Divider, Typography } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import JSONViewer from 'components/elements/display/json/JSONViewer';
import HitBanner from 'components/elements/hit/HitBanner';
import { HitLayout } from 'components/elements/hit/HitLayout';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const HitBannerDocumentation: FC = () => {
  const { t } = useTranslation();

  const dummyHit = useMemo<Hit>(
    () => ({
      timestamp: '2023-02-11T15:10:31.585826Z',
      howler: {
        id: 'howler.id',
        analytic: 'howler.analytic',
        detection: 'howler.detection',
        assignment: 'howler.assignment',
        hash: 'howler.hash',
        outline: {
          threat: 'howler.outline.threat',
          target: 'howler.outline.target',
          indicators: ['howler.outline.indicators'],
          summary: 'howler.outline.summary'
        },
        escalation: 'howler.escalation',
        status: 'howler.status'
      },
      event: {
        created: '2023-02-11T15:10:31.585826Z',
        provider: 'event.provider'
      },
      organization: {
        id: 'organization.id',
        name: 'organization.name'
      },
      threat: {
        tactic: {
          id: 'threat.tactic.id',
          name: 'threat.tactic.name'
        },
        technique: {
          id: 'threat.technique.id',
          name: 'threat.technique.name'
        }
      }
    }),
    []
  );

  return (
    <>
      <h1>{t('help.hit.banner.title')}</h1>
      <Typography variant="body1">{t('help.hit.banner.description')}</Typography>
      <Divider orientation="horizontal" sx={{ my: 2 }} />
      <HowlerCard sx={{ mb: 2 }}>
        <CardContent>
          <HitBanner hit={dummyHit} layout={HitLayout.COMFY} />
        </CardContent>
      </HowlerCard>
      <Typography variant="body1">{t('help.hit.banner.json')}</Typography>
      <Divider orientation="horizontal" sx={{ my: 2 }} />
      <JSONViewer data={dummyHit} />
    </>
  );
};

export default HitBannerDocumentation;

import { Card, CardContent, Stack } from '@mui/material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { HitLayout } from 'components/elements/hit/HitLayout';
import HitOutline from 'components/elements/hit/HitOutline';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import dayjs from 'dayjs';
import howlerPluginStore from 'plugins/store';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import type { Template } from 'models/entities/generated/Template';
import { usePluginStore } from 'react-pluggable';
import { modifyDocumentation } from 'utils/utils';
import TEMPLATES_EN from './markdown/en/templates.md';
import TEMPLATES_FR from './markdown/fr/templates.md';

const TEMPLATE: Template = {
  analytic: 'Cat Checker',
  owner: 'cat',
  type: 'personal'
};

const ALERTS = [
  {
    howler: { id: 'hit1', analytic: 'Cat Checker', detection: 'Listening for Meows' },
    event: {
      start: dayjs().subtract(4, 'hour').toString(),
      end: dayjs().subtract(3, 'hour').toString(),
      kind: 'Loud meow',
      outcome: 'Food provided'
    }
  },
  {
    howler: { id: 'hit2', analytic: 'Cat Checker', detection: 'Looking for paw prints' },
    event: {
      start: dayjs().subtract(6, 'hour').toString(),
      end: dayjs().subtract(5, 'hour').toString(),
      provider: "The neighbour's cat (probably)",
      reason: 'There was some fish we forgot to put away in the kitchen'
    }
  }
];

const TemplateDocumentation: FC = () => {
  const { i18n } = useTranslation();
  const pluginStore = usePluginStore();
  useScrollRestoration();

  const [md1, md2] = useMemo(() => {
    let markdown = i18n.language === 'en' ? TEMPLATES_EN : TEMPLATES_FR;

    markdown = markdown.replace(/\$CURRENT_URL/g, window.location.origin);

    ALERTS.forEach((alert, index) => {
      markdown = markdown.replace(`$ALERT_${index + 1}`, JSON.stringify(alert, null, 2));
    });

    return markdown
      .split('\n===SPLIT===\n')
      .map(section => modifyDocumentation(section, howlerPluginStore, pluginStore));
  }, [i18n.language, pluginStore]);

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown md={md1} />
      <Stack spacing={1}>
        {ALERTS.map(alert => (
          <Card key={alert.howler.id} variant="outlined">
            <CardContent>
              <HitOutline
                hit={alert as any}
                template={{
                  ...TEMPLATE,
                  detection: alert.howler.detection,
                  keys: Object.keys(alert['event']).map(key => `event.${key}`)
                }}
                layout={HitLayout.NORMAL}
                forceAllFields
              />
            </CardContent>
          </Card>
        ))}
      </Stack>
      <Markdown md={md2} />
    </PageCenter>
  );
};
export default TemplateDocumentation;

import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Skeleton } from '@mui/material';
import api from 'api';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import howlerPluginStore from 'plugins/store';
import { usePluginStore } from 'react-pluggable';
import { modifyDocumentation } from 'utils/utils';
import AUTH_EN from './markdown/en/retention.md';
import AUTH_FR from './markdown/fr/retention.md';

const RetentionDocumentation: FC = () => {
  const { i18n } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const pluginStore = usePluginStore();
  useScrollRestoration();

  const [hitId, setHitId] = useState<string>();

  const md = useMemo(() => {
    let original = (i18n.language === 'en' ? AUTH_EN : AUTH_FR).replace(/\$CURRENT_URL/g, window.location.origin);

    return modifyDocumentation(original, howlerPluginStore, pluginStore);
  }, [i18n.language, pluginStore]);

  useEffect(() => {
    api.search.hit
      .post({
        query: 'howler.id:*',
        sort: 'event.created asc',
        rows: 1,
        fl: 'howler.id'
      })
      .then(val => setHitId(val.items[0].howler.id));
  });

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown
        md={md}
        components={{
          duration: (
            <span>
              {config.configuration.system.retention.limit_amount} {config.configuration.system.retention.limit_unit}
            </span>
          ),
          alert: hitId ? <HitCard layout={HitLayout.DENSE} id={hitId} /> : <Skeleton variant="rounded" height="250px" />
        }}
      />
    </PageCenter>
  );
};
export default RetentionDocumentation;

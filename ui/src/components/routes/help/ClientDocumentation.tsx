import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import CLIENT_EN from './markdown/en/client.md';
import CLIENT_FR from './markdown/fr/client.md';

const ClientDocumentation: FC = () => {
  const { i18n } = useTranslation();
  useScrollRestoration();

  const md = useMemo(
    () => (i18n.language === 'en' ? CLIENT_EN : CLIENT_FR).replace(/\$CURRENT_URL/g, window.location.origin),
    [i18n.language]
  );

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown md={md} />
    </PageCenter>
  );
};

export default ClientDocumentation;

import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import howlerPluginStore from 'plugins/store';
import { usePluginStore } from 'react-pluggable';
import { modifyDocumentation } from 'utils/utils';
import AUTH_EN from './markdown/en/authentication.md';
import AUTH_FR from './markdown/fr/authentication.md';

const AuthDocumentation: FC = () => {
  const { i18n } = useTranslation();
  const pluginStore = usePluginStore();
  useScrollRestoration();

  const md = useMemo(() => {
    let original = (i18n.language === 'en' ? AUTH_EN : AUTH_FR).replace(/\$CURRENT_URL/g, window.location.origin);

    return modifyDocumentation(original, howlerPluginStore, pluginStore);
  }, [i18n.language, pluginStore]);

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown md={md} />
    </PageCenter>
  );
};
export default AuthDocumentation;

import Markdown from 'components/elements/display/Markdown';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import LINKS_EN from './markdown/en/links.md';
import LINKS_FR from './markdown/fr/links.md';

const HitLinksDocumentation: FC = () => {
  const { i18n } = useTranslation();

  const { config } = useContext(ApiConfigContext);

  const md = useMemo(() => {
    const appList = config.configuration.ui.apps.map(a => `- \`${a.name.toLowerCase()}\``).join('\n');

    return (i18n.language === 'en' ? LINKS_EN : LINKS_FR).replace('$APP_LIST', appList);
  }, [config.configuration.ui.apps, i18n.language]);

  return <Markdown md={md} />;
};
export default HitLinksDocumentation;

import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import howlerPluginStore from 'plugins/store';
import { useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { modifyDocumentation } from 'utils/utils';
import NOTEBOOK_EN from './markdown/en/notebook.md';
import NOTEBOOK_FR from './markdown/fr/notebook.md';

const NotebookDocumentation: FC = () => {
  const { i18n } = useTranslation();
  const pluginStore = usePluginStore();
  useScrollRestoration();

  const md = useMemo(() => {
    let markdown = (i18n.language === 'en' ? NOTEBOOK_EN : NOTEBOOK_FR)
      .replaceAll(
        '$NBGALLERY_URL',
        window.location.host.startsWith('localhost')
          ? 'https://nbgallery.dev.analysis.cyber.gc.ca'
          : window.location.origin.replace(/howler(-stg)/, 'nbgallery')
      )
      .replaceAll('$CURRENT_URL', window.location.origin);

    return modifyDocumentation(markdown, howlerPluginStore, pluginStore);
  }, [i18n.language, pluginStore]);

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown md={md} />
    </PageCenter>
  );
};
export default NotebookDocumentation;

import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import NOTEBOOK_EN from './markdown/en/notebook.md';
import NOTEBOOK_FR from './markdown/fr/notebook.md';

const NotebookDocumentation: FC = () => {
  const { i18n } = useTranslation();
  useScrollRestoration();

  const markdown = (i18n.language === 'en' ? NOTEBOOK_EN : NOTEBOOK_FR)
    .replaceAll(
      '$NBGALLERY_URL',
      window.location.host.startsWith('localhost')
        ? 'https://nbgallery.example.com'
        : window.location.origin.replace(/howler(-stg)/, 'nbgallery')
    )
    .replaceAll('$CURRENT_URL', window.location.origin);

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown md={markdown} />
    </PageCenter>
  );
};
export default NotebookDocumentation;

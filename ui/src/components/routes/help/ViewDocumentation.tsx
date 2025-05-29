import { Search } from '@mui/icons-material';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import VIEWS_EN from './markdown/en/views.md';
import VIEWS_FR from './markdown/fr/views.md';

const ViewDocumentation: FC = () => {
  const { i18n } = useTranslation();
  useScrollRestoration();

  const md = useMemo(
    () => (i18n.language === 'en' ? VIEWS_EN : VIEWS_FR).replace(/\$CURRENT_URL/g, window.location.origin),
    [i18n.language]
  );

  return (
    <PageCenter margin={4} width="100%" textAlign="left">
      <Markdown
        md={md}
        components={{
          search: <Search fontSize="inherit" />
        }}
      />
    </PageCenter>
  );
};
export default ViewDocumentation;

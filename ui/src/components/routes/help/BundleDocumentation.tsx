import Markdown from 'components/elements/display/Markdown';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import BUNDLES_EN from './markdown/en/bundles.md';
import BUNDLES_FR from './markdown/fr/bundles.md';

const BundleDocumentation: FC = () => {
  const { i18n } = useTranslation();

  const md = useMemo(() => (i18n.language === 'en' ? BUNDLES_EN : BUNDLES_FR), [i18n.language]);

  return <Markdown md={md} />;
};

export default BundleDocumentation;

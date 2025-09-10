import { useHelpers } from 'components/elements/display/handlebars/helpers';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import TEMPLATE_EN from './template/en.md';
import TEMPLATE_FR from './template/fr.md';

const TEMPLATES = {
  en: TEMPLATE_EN,
  fr: TEMPLATE_FR
};

export const useStartingTemplate = () => {
  const helpers = useHelpers();
  const { i18n } = useTranslation();

  const helperText = useMemo(
    () =>
      helpers
        .map(helper =>
          `
### \`${helper.keyword}\`

${helper.documentation[i18n.language]}

---
`.trim()
        )
        .join('\n'),
    [helpers, i18n.language]
  );

  return useMemo(
    () => `
${TEMPLATES[i18n.language]}

${helperText}
`,
    [helperText, i18n.language]
  );
};

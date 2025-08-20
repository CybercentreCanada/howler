import { useHelpers } from 'components/elements/display/handlebars/helpers';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import templateEn from './template.en.md';
import templateFr from './template.fr.md';

const OVERVIEW = {
  en: templateEn,
  fr: templateFr
};

export const useStartingTemplate = () => {
  const { i18n } = useTranslation();
  const helpers = useHelpers();

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
${OVERVIEW[i18n.language]}

${helperText}
`,
    [helperText, i18n.language]
  );
};

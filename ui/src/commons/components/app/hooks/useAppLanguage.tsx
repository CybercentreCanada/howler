import { AppContext } from 'commons/components/app/AppContexts';
import i18n from 'i18n';
import { useContext, useEffect, useMemo } from 'react';

export type AppLanguageType = {
  isFR: () => boolean;
  isEN: () => boolean;
  toggle: () => void;
};

export function useAppLanguage(onChange?: (language: 'en' | 'fr') => void): AppLanguageType {
  const { toggleLanguage } = useContext(AppContext);

  useEffect(() => {
    if (onChange) {
      i18n.on('languageChanged', onChange);
    }
    return () => {
      if (onChange) {
        i18n.off('languageChanged', onChange);
      }
    };
  }, [onChange]);

  return useMemo(
    () => ({ isFR: () => i18n.language === 'fr', isEN: () => i18n.language === 'en', toggle: toggleLanguage }),
    [toggleLanguage]
  );
}

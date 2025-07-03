import { createInstance, type i18n } from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import helpMainEN from 'locales/en/help/main.json';
import helpSearchEN from 'locales/en/help/search.json';
import translationEN from 'locales/en/translation.json';
import helpMainFR from 'locales/fr/help/main.json';
import helpSearchFR from 'locales/fr/help/search.json';
import translationFR from 'locales/fr/translation.json';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: translationEN,
    helpSearch: helpSearchEN,
    helpMain: helpMainEN
  },
  fr: {
    translation: translationFR,
    helpSearch: helpSearchFR,
    helpMain: helpMainFR
  },
  woof: {
    translation: Object.keys(translationEN).reduce(
      (acc, key) => {
        acc[key] = 'woof';
        return acc;
      },
      {} as { [key: string]: string }
    )
  }
};

const i18nInstance: i18n = createInstance();

i18nInstance
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    keySeparator: false,
    interpolation: {
      escapeValue: false
    },
    detection: {
      order: ['localStorage', 'cookie']
    },
    resources
  });

export default i18nInstance;

import type { i18n as I18N } from 'i18next';
import HowlerPlugin from 'plugins/HowlerPlugin';
import AnalystPresenceToolbarButtonContent from './components/AnalystPresenceToolbarButton';
import tsxAnalystPresenceEN from './locales/tsx_analyst_presence.en.json';

class TSXAnalystPresence extends HowlerPlugin {
  name = 'tsx_analyst_presence';
  version = '1.0.0';
  author = 'Truesec';
  description = 'A plugin to show analyst presence.';

  activate(): void {
    super.activate();
    super.addAppBarItem(<AnalystPresenceToolbarButtonContent />);
  }

  localization(i18nInstance: I18N) {
    i18nInstance.addResourceBundle('en', 'translation', tsxAnalystPresenceEN, true, true);
  }

  deactivate(): void {
    super.deactivate();
  }
}

export default TSXAnalystPresence;

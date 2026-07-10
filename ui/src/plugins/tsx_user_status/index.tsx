import type { i18n } from 'i18next';
import HowlerPlugin from 'plugins/HowlerPlugin';
import { UserStatusToolbarButton } from './components/UserStatusToolbarButton';
import tsxUserStatusEN from './locales/tsx_user_status.en.json';

class TSXUserStatus extends HowlerPlugin {
  name = 'Truesec User Status';
  version = '1.0.0';
  author = 'Truesec';
  description = 'Truesec custom plugin to display and manage user team, shift and status';

  activate() {
    super.activate();
    super.addAppBarItem(<UserStatusToolbarButton />);
  }

  localization(i18nInstance: i18n) {
    i18nInstance.addResourceBundle('en', 'translation', tsxUserStatusEN, true, true);
  }

  deactivate() {
    super.deactivate();
  }
}

export default TSXUserStatus;

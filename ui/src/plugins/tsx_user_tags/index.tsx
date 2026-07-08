import type { i18n as I18N } from 'i18next';
import HowlerPlugin from 'plugins/HowlerPlugin';
import { UserTagsProvider } from './components/UserTagsContext';
import { UserTagsToolbarButton } from './components/UserTagsToolbarButton';
import tsxUserTagsEN from './locales/tsx_user_tags.en.json';

class TSXUserTags extends HowlerPlugin {
  name = 'tsx_user_tags';
  version = '0.1.0';
  author = 'Truesec';
  description = 'Allow analysts to manage personal tags';

  static shouldLoad(): boolean {
    const checkPluginStatus = async (): Promise<boolean> => {
      const alive = await fetch('/api/v1/tags/healthz/live');
      const ready = await fetch('/api/v1/tags/healthz/ready');

      return alive.ok && ready.ok;
    };

    checkPluginStatus().then(isReady => {
      if (isReady) {
        return true;
      } else {
        return false;
      }
    });
    return false;
  }

  activate(): void {
    super.activate();
    super.addAppBarItem(
      <UserTagsProvider>
        <UserTagsToolbarButton />
      </UserTagsProvider>
    );
  }

  localization(i18nInstance: I18N) {
    i18nInstance.addResourceBundle('en', 'translation', tsxUserTagsEN, true, true);
  }

  deactivate(): void {
    super.deactivate();
  }
}

export default TSXUserTags;

import '@fontsource/roboto';
import App from 'components/app/App';
import 'i18n';
import 'index.css';
import howlerPluginStore from 'plugins/store';
import TSXUserTags from 'plugins/tsx_user_tags';
import * as ReactDOM from 'react-dom/client';
import TSXAnalystPresence from './plugins/tsx_analyst_presence';
import TSXUserStatus from './plugins/tsx_user_status';

// This is where you can inject UI plugins to modify Howler's interface.
// howlerPluginStore.install(new ExamplePlugin());

if (import.meta.env.VITE_ENABLE_CLUE === 'true') {
  const cluePlugin = await import('plugins/clue');

  howlerPluginStore.install(new cluePlugin.default());
}

howlerPluginStore.install(new TSXUserStatus());
howlerPluginStore.install(new TSXAnalystPresence());
howlerPluginStore.install(new TSXUserTags());

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

import '@fontsource/roboto';
import App from 'components/app/App';
import 'i18n';
import 'index.css';
import HowlerPlugin from 'plugins/HowlerPlugin';
import howlerPluginStore from 'plugins/store';
// import howlerPluginStore from 'plugins/store';
import * as ReactDOM from 'react-dom/client';

// This is where you can inject UI plugins to modify Howler's interface.
// howlerPluginStore.install(new ExamplePlugin());

class DocumentationDummy extends HowlerPlugin {
  name = 'DocumentationDummy';
  version = '0.0.1';
  author = 'Taha Shahid <taha.shahid@cse-cst.gc.ca>';
  description = 'This plugin enables CCCS-specific documentation functionality in Howler.';

  documentation(md: string): string {
    // Ignore in PR: Only for specific route location
    return md;
  }
}

howlerPluginStore.install(new DocumentationDummy());

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

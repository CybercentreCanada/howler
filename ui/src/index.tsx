import '@fontsource/roboto';
import App from 'components/app/App';
import 'i18n';
import 'index.css';
// import howlerPluginStore from 'plugins/store';
import * as ReactDOM from 'react-dom/client';

// This is where you can inject UI plugins to modify Howler's interface.
// howlerPluginStore.install(new ExamplePlugin());

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

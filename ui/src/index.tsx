import '@fontsource/roboto';
import App from 'components/app/App';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import 'i18n';
import 'index.css';
// import howlerPluginStore from 'plugins/store';
import * as ReactDOM from 'react-dom/client';

dayjs.extend(utc);
dayjs.extend(duration);
dayjs.extend(relativeTime);

// This is where you can inject UI plugins to modify Howler's interface.
// howlerPluginStore.install(new ExamplePlugin());

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

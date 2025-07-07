import { Box } from '@mui/material';
import { Fetcher } from 'borealis-ui';
import borealisEN from 'borealis-ui/dist/en/translation.json';
import borealisFR from 'borealis-ui/dist/fr/translation.json';
import type { HowlerHelper } from 'components/elements/display/handlebars/helpers';
import type { PluginChipProps } from 'components/elements/PluginChip';
import type { PluginTypographyProps } from 'components/elements/PluginTypography';
import { type i18n as I18N } from 'i18next';
import HowlerPlugin from 'plugins/HowlerPlugin';
import BorealisChip from './components/BorealisChip';
import BorealisLeadForm from './components/BorealisLeadForm';
import BorealisPivot from './components/BorealisPivot';
import BorealisPivotForm from './components/BorealisPivotForm';
import BorealisTypography from './components/BorealisTypography';
import HELPERS from './helpers';
import Provider from './Provider';
import useSetup from './setup';

class BorealisPlugin extends HowlerPlugin {
  name = 'BorealisPlugin';
  version = '0.0.1';
  author = 'Matthew Rafuse <matthew.rafuse@cyber.gc.ca>';
  description = 'This plugin enables borealis enrichment in Howler.';

  activate(): void {
    super.activate();

    super.addLead(
      'borealis',
      props => <BorealisLeadForm {...props} />,
      (content: string, metadata: string) => (
        <Box p={1} flex={1} display="flex" alignItems="stretch">
          <Fetcher fetcherId={content} {...JSON.parse(metadata)} />
        </Box>
      )
    );

    super.addPivot(
      'borealis',
      props => <BorealisPivotForm {...props} />,
      props => <BorealisPivot {...props} />
    );
  }

  provider() {
    return Provider;
  }

  setup() {
    return useSetup;
  }

  localization(i18nInstance: I18N) {
    i18nInstance.addResourceBundle('en', 'borealis', borealisEN, true, true);
    i18nInstance.addResourceBundle('fr', 'borealis', borealisFR, true, true);
  }

  helpers(): HowlerHelper[] {
    return HELPERS;
  }

  typography(_props: PluginTypographyProps) {
    return <BorealisTypography {..._props} />;
  }

  chip(_props: PluginChipProps) {
    return <BorealisChip {..._props} />;
  }
}

export default BorealisPlugin;

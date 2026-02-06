import Fetcher from '@cccsaurora/clue-ui/components/fetchers/Fetcher';
import clueEN from '@cccsaurora/clue-ui/en/translation.json';
import clueFR from '@cccsaurora/clue-ui/fr/translation.json';
import { Box } from '@mui/material';
import type { HowlerHelper } from 'components/elements/display/handlebars/helpers';
import type { PivotLinkProps } from 'components/elements/hit/related/PivotLink';
import type { PluginChipProps } from 'components/elements/PluginChip';
import type { PluginTypographyProps } from 'components/elements/PluginTypography';
import type { PivotFormProps } from 'components/routes/dossiers/PivotForm';
import { type i18n as I18N } from 'i18next';
import get from 'lodash-es/get';
import type { Hit } from 'models/entities/generated/Hit';
import HowlerPlugin from 'plugins/HowlerPlugin';
import ClueChip from './components/ClueChip';
import ClueLeadForm from './components/ClueLeadForm';
import CluePivot from './components/CluePivot';
import CluePivotForm from './components/CluePivotForm';
import ClueTypography from './components/ClueTypography';
import HELPERS from './helpers';
import howlerClueEN from './locales/clue.en.json';
import howlerClueFR from './locales/clue.fr.json';
import Provider from './Provider';
import useSetup from './setup';

class CluePlugin extends HowlerPlugin {
  name = 'CluePlugin';
  version = '0.0.1';
  author = 'Matthew Rafuse <matthew.rafuse@cyber.gc.ca>';
  description = 'This plugin enables clue enrichment in Howler.';

  activate(): void {
    super.activate();

    const leadForm = props => <ClueLeadForm {...props} />;
    const leadRenderer = (content: string, metadata: string, hit: Hit) => {
      const parsedProps = JSON.parse(metadata);

      const value = get(hit, parsedProps.value);

      if (Array.isArray(value)) {
        // TODO: Revisit handling for array values
        parsedProps.value = value[0];
      } else {
        parsedProps.value = value;
      }

      return (
        <Box p={1} flex={1} display="flex" alignItems="stretch">
          <Fetcher fetcherId={content} {...parsedProps} />
        </Box>
      );
    };

    super.addLead('clue', leadForm, leadRenderer);

    const pivotForm = (props: PivotFormProps) => <CluePivotForm {...props} />;
    const pivotRenderer = (props: PivotLinkProps) => <CluePivot {...props} />;

    super.addPivot('clue', pivotForm, pivotRenderer);
  }

  provider() {
    return Provider;
  }

  setup() {
    return useSetup;
  }

  localization(i18nInstance: I18N) {
    i18nInstance.addResourceBundle('en', 'clue', clueEN, true, true);
    i18nInstance.addResourceBundle('fr', 'clue', clueFR, true, true);

    i18nInstance.addResourceBundle('en', 'translation', howlerClueEN, true, false);
    i18nInstance.addResourceBundle('fr', 'translation', howlerClueFR, true, false);
  }

  helpers(): HowlerHelper[] {
    return HELPERS;
  }

  typography(_props: PluginTypographyProps) {
    return <ClueTypography {..._props} />;
  }

  chip(_props: PluginChipProps) {
    return <ClueChip {..._props} />;
  }
}

export default CluePlugin;

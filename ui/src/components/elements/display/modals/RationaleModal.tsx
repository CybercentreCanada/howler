import { Autocomplete, Button, CircularProgress, ListItemText, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import type { HowlerFacetSearchRequest } from 'api/search/facet';
import { useAppUser } from 'commons/components/app/hooks/useAppUser';
import { parseEvent } from 'commons/components/utils/keyboard';
import useMatchers from 'components/app/hooks/useMatchers';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import { isEqual, uniqBy } from 'lodash-es';
import isString from 'lodash-es/isString';
import type { Hit } from 'models/entities/generated/Hit';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

/**
 * Represents a suggested rationale option with its source type.
 * - assignment: Rationales previously used by the current user
 * - analytic: Rationales used by others for the same analytic
 * - preset: Predefined rationales from the analytic configuration
 */
interface RationaleOption {
  type: 'assignment' | 'analytic' | 'preset';
  rationale: string;
}

const RationaleModal: FC<{ hits: Hit[]; onSubmit: (rationale: string) => void }> = ({ hits, onSubmit }) => {
  // Hooks for translations, API calls, modal control, user data, and analytic matching
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);
  const { user } = useAppUser<HowlerUser>();
  const { getMatchingAnalytic } = useMatchers();

  // State management for loading status, user input, and suggested options
  const [loading, setLoading] = useState(false);
  const [rationale, setRationale] = useState('');
  const [suggestedRationales, setSuggestedRationales] = useState<RationaleOption[]>([]);

  /**
   * Submits the rationale and closes the modal
   */
  const handleSubmit = useCallback(() => {
    onSubmit(rationale);
    close();
  }, [onSubmit, rationale, close]);

  /**
   * Handles keyboard shortcuts:
   * - Ctrl+Enter: Submit the rationale
   * - Escape: Close the modal
   */
  const handleKeydown = useCallback(
    e => {
      const parsedEvent = parseEvent(e);

      if (parsedEvent.isCtrl && parsedEvent.isEnter) {
        handleSubmit();
      } else if (parsedEvent.isEscape) {
        close();
      }
    },
    [close, handleSubmit]
  );

  /**
   * Executes a facet search to retrieve rationales from existing hits
   * @param request - The facet search request parameters
   * @param type - The type of rationale source (assignment/analytic)
   * @returns Array of rationale options with their type
   */
  const runFacet = useCallback(
    async (request: HowlerFacetSearchRequest, type: RationaleOption['type']): Promise<RationaleOption[]> => {
      const result = await dispatchApi(api.search.facet.hit.post(request), { throwError: false });

      if (!result?.['howler.rationale']) {
        return [];
      }

      return Object.keys(result['howler.rationale'] ?? {}).map(_rationale => ({
        rationale: _rationale,
        type
      }));
    },
    [dispatchApi]
  );

  /**
   * Fetches preset rationales from the analytic configurations.
   * Retrieves matching analytics for the provided hits and extracts their predefined rationales.
   */
  const fetchPresetRationales = useCallback(async (): Promise<RationaleOption[]> => {
    const analytics = await Promise.all(hits.flatMap(hit => getMatchingAnalytic(hit)));
    const uniqueAnalytics = uniqBy(analytics, 'analytic_id');
    const rationales = uniqueAnalytics.flatMap(_analytic => _analytic?.triage_settings?.rationales ?? []);

    return rationales.map(_rationale => ({ rationale: _rationale, type: 'preset' as const }));
  }, [hits, getMatchingAnalytic]);

  useEffect(() => {
    (async () => {
      setLoading(true);

      const options: RationaleOption[][] = await Promise.all([
        fetchPresetRationales(),
        // Rationales by other users for the current analytic
        runFacet(
          {
            query: 'howler.rationale:*',
            rows: 10,
            fields: ['howler.rationale'],
            filters: hits.map(hit => `howler.analytic:"${sanitizeLuceneQuery(hit.howler.analytic)}")`)
          },
          'analytic'
        ),
        // Rationales provided by this user
        runFacet(
          {
            query: `howler.rationale:* AND howler.assignment:${user.username} AND timestamp:[now-14d TO now]`,
            rows: 25,
            fields: ['howler.rationale']
          },
          'assignment'
        )
      ]);

      setSuggestedRationales(options.flat());
      setLoading(false);
    })();
  }, [dispatchApi, fetchPresetRationales, getMatchingAnalytic, hits, runFacet, user.username]);

  // Render the modal with title, description, autocomplete input, and action buttons
  return (
    <Stack spacing={2} p={2} alignItems="start" sx={{ minWidth: '500px' }}>
      <Typography variant="h4">{t('modal.rationale.title')}</Typography>
      <Typography>{t('modal.rationale.description')}</Typography>
      {/* Autocomplete field with suggested rationales and free text input */}
      <Autocomplete
        loading={loading}
        loadingText={t('loading')}
        freeSolo
        value={rationale}
        onChange={(_, newValue) => setRationale(isString(newValue) ? newValue : (newValue?.rationale ?? ''))}
        options={suggestedRationales}
        getOptionLabel={suggestion => (isString(suggestion) ? suggestion : suggestion.rationale)}
        isOptionEqualToValue={(option, value) =>
          isString(value) ? option.rationale === value : isEqual(option, value)
        }
        fullWidth
        disablePortal
        renderInput={params => (
          <TextField
            {...params}
            label={t('modal.rationale.label')}
            onChange={e => setRationale(e.target.value)}
            onKeyDown={handleKeydown}
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {loading ? <CircularProgress color="inherit" size={20} /> : null}
                  {params.InputProps.endAdornment}
                </>
              )
            }}
          />
        )}
        renderOption={(props, option) => (
          <ListItemText
            {...(props as any)}
            sx={{ flexDirection: 'column', alignItems: 'start !important' }}
            primary={option.rationale}
            secondary={t(`modal.rationale.type.${option.type}`)}
          />
        )}
      />

      <Stack direction="row" spacing={1} alignSelf="end">
        <Button variant="outlined" onClick={close}>
          {t('cancel')}
        </Button>
        <Button variant="outlined" onClick={handleSubmit}>
          {t('submit')}
        </Button>
      </Stack>
    </Stack>
  );
};

export default RationaleModal;

import { Autocomplete, Button, CircularProgress, ListItemText, Stack, TextField, Typography } from '@mui/material';
import api from 'api';
import { useAppUser } from 'commons/components/app/hooks/useAppUser';
import { parseEvent } from 'commons/components/utils/keyboard';
import { ModalContext } from 'components/app/providers/ModalProvider';
import useMyApi from 'components/hooks/useMyApi';
import { isEqual } from 'lodash-es';
import flatten from 'lodash-es/flatten';
import isString from 'lodash-es/isString';
import uniqBy from 'lodash-es/uniqBy';
import type { Hit } from 'models/entities/generated/Hit';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

const RationaleModal: FC<{ hits: Hit[]; onSubmit: (rationale: string) => void }> = ({ hits, onSubmit }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { close } = useContext(ModalContext);
  const { user } = useAppUser<HowlerUser>();

  const [loading, setLoading] = useState(false);
  const [rationale, setRationale] = useState('');

  const [suggestedRationales, setSuggestedRationales] = useState<
    { type: 'assignment' | 'analytic'; rationale: string }[]
  >([]);

  const queries = useMemo(
    () => [
      {
        type: 'analytic' as const,
        query: hits
          .map(hit => `(howler.rationale:* AND howler.analytic:"${sanitizeLuceneQuery(hit.howler.analytic)}")`)
          .join(' OR ')
      },
      {
        type: 'assignment' as const,
        query: `howler.rationale:* AND howler.assignment:${user.username} AND howler.timestamp:[now-14d TO now]`
      }
    ],
    [hits, user.username]
  );

  const handleSubmit = useCallback(() => {
    onSubmit(rationale);
    close();
  }, [onSubmit, rationale, close]);

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

  useEffect(() => {
    (async () => {
      setLoading(true);
      // TOOD: Eventually switch a a facet call once the elasticsearch refactor is complete
      const results = flatten(
        await Promise.all(
          queries.map(async ({ query, type }) => {
            const result = await dispatchApi(
              api.search.hit.post({ query, rows: 250, fl: 'howler.rationale,howler.assignment' }),
              { throwError: false }
            );

            return uniqBy(
              (result?.items ?? []).map(_hit => ({ rationale: _hit.howler.rationale, type })),
              'rationale'
            );
          })
        )
      );

      setSuggestedRationales(results);
      setLoading(false);
    })();
  }, [dispatchApi, queries]);

  return (
    <Stack spacing={2} p={2} alignItems="start" sx={{ minWidth: '500px' }}>
      <Typography variant="h4">{t('modal.rationale.title')}</Typography>
      <Typography>{t('modal.rationale.description')}</Typography>
      <Autocomplete
        loading={loading}
        loadingText={t('loading')}
        freeSolo
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

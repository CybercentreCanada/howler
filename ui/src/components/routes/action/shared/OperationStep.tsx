import {
  Alert,
  AlertTitle,
  Autocomplete,
  CircularProgress,
  InputAdornment,
  LinearProgress,
  Stack,
  TextField
} from '@mui/material';
import api from 'api';
import type { HowlerSearchResponse } from 'api/search';
import useMyApi from 'components/hooks/useMyApi';
import { capitalize } from 'lodash-es';
import type { ActionOperationStep } from 'models/ActionTypes';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { checkArgsAreFilled, getArgsByContext, getOptionsByContext } from 'utils/actionUtils';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import Throttler from 'utils/Throttler';

const THROTTLER = new Throttler(500);

const OperationStep: FC<{
  readonly?: boolean;
  loading?: boolean;
  query: string;
  step: ActionOperationStep;
  values: string;
  setValues?: (values: string) => void;
}> = ({ step, query, values, setValues, readonly, loading }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [validating, setValidating] = useState(false);
  const [warnResponse, setWarnResponse] = useState<HowlerSearchResponse<Hit>>(null);
  const [errorResponse, setErrorResponse] = useState<HowlerSearchResponse<Hit>>(null);

  const filled = useMemo(() => checkArgsAreFilled(step, values), [step, values]);
  const validationStatus = useMemo(
    () =>
      errorResponse?.total > 0
        ? 'error'
        : warnResponse?.total > 0
          ? 'warning'
          : errorResponse || warnResponse
            ? 'success'
            : null,
    [errorResponse, warnResponse]
  );

  const args = useMemo(() => getArgsByContext(step.args, values), [step.args, values]);
  const parsedValues = useMemo(() => JSON.parse(values), [values]);

  /**
   * Substitute the current user values into a given validation query
   */
  const substitute = useCallback(
    (_query: string) =>
      Object.entries(values).reduce((q, [key, val]) => q.replace(`$${key}`, sanitizeLuceneQuery(val)), _query),
    [values]
  );

  /**
   * Get a well formatted label based on the argument key
   */
  const getLabel = useCallback(
    (argId?: string) =>
      (argId ?? '')
        .replace(/[-_]/g, ' ')
        .split(' ')
        .map(part => capitalize(part))
        .join(' '),
    []
  );

  /**
   * Run validation on the data provided for this step of the operation
   */
  const validate = useCallback(async () => {
    if (!query || readonly) {
      return;
    }

    try {
      setValidating(true);

      if (step.validation?.warn) {
        const result = await dispatchApi(
          api.search.hit.post({
            query: `(${query}) AND (${substitute(step.validation.warn.query)})`
          }),
          { throwError: false }
        );

        setWarnResponse(result);
      }

      if (step.validation?.error) {
        const result = await dispatchApi(
          api.search.hit.post({
            query: `(${query}) AND (${substitute(step.validation.error.query)})`
          }),
          { throwError: false }
        );

        setErrorResponse(result);
      }
    } finally {
      setValidating(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step.validation?.error, step.validation?.warn, dispatchApi, query, substitute]);

  useEffect(() => {
    if (validating || !filled || !step.validation) {
      return;
    }

    THROTTLER.debounce(validate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filled, validate, query, values]);

  return (
    <Stack spacing={2}>
      {args.map(arg => {
        if (step.options?.[arg]) {
          const opts = getOptionsByContext(step.options, arg, values);

          return (
            <Autocomplete
              disablePortal
              key={arg}
              options={opts}
              disabled={readonly || loading}
              value={parsedValues?.[arg] || ''}
              renderInput={params => (
                <TextField
                  {...params}
                  InputProps={{
                    ...params.InputProps,
                    startAdornment: loading && (
                      <InputAdornment position="start">
                        <CircularProgress size={24} />
                      </InputAdornment>
                    )
                  }}
                  label={getLabel(arg)}
                />
              )}
              onChange={(_, value) => setValues(JSON.stringify({ ...parsedValues, [arg]: value }))}
            />
          );
        } else {
          return (
            <TextField
              key={arg}
              disabled={readonly}
              value={parsedValues?.[arg] || ''}
              onChange={e => setValues(JSON.stringify({ ...parsedValues, [arg]: e.target.value }))}
              label={getLabel(arg)}
            />
          );
        }
      })}
      {filled && (
        <>
          {validating && <LinearProgress />}
          {validationStatus && (
            <Alert
              variant="outlined"
              severity={validationStatus}
              sx={{
                '& > code': { fontSize: '0.9em' },
                '& a': {
                  color: validationStatus,
                  '&:visited': {
                    color: validationStatus
                  },
                  '&:not(:hover)': { textDecoration: 'none' }
                }
              }}
            >
              <AlertTitle>
                {t(
                  (validationStatus === 'error' ? step.validation.error?.message : step.validation.warn?.message) ??
                    `route.actions.alert.${validationStatus}`,
                  {
                    count: validationStatus === 'error' ? errorResponse.total : warnResponse?.total
                  }
                )}
              </AlertTitle>
              {validationStatus !== 'success' && (
                <Link
                  to={`/hits?query=${encodeURIComponent(
                    errorResponse?.total
                      ? substitute(step.validation.error.query)
                      : warnResponse?.total && substitute(step.validation.warn.query)
                  )}`}
                >
                  {errorResponse?.total ? (
                    <code>{substitute(step.validation.error.query)}</code>
                  ) : (
                    warnResponse?.total && <code>{substitute(step.validation.warn.query)}</code>
                  )}
                </Link>
              )}
            </Alert>
          )}
        </>
      )}
    </Stack>
  );
};

export default OperationStep;

import ReactJson, { type CollapsedFieldProps } from '@microlink/react-json-view';
import { Clear } from '@mui/icons-material';
import { IconButton, Skeleton, Stack } from '@mui/material';
import { useAppTheme } from 'commons/components/app/hooks';
import Phrase from 'components/elements/addons/search/phrase/Phrase';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';
import Throttler from 'utils/Throttler';
import { removeEmpty, searchObject } from 'utils/utils';

const THROTTLER = new Throttler(150);

const JSONViewer: FC<{ data: object; collapse?: boolean }> = ({ data, collapse = true }) => {
  const { t } = useTranslation();
  const { isDark } = useAppTheme();
  const [compact] = useMyLocalStorageItem<boolean>(StorageKey.COMPACT_JSON, true);
  const [flat] = useMyLocalStorageItem<boolean>(StorageKey.FLATTEN_JSON);

  const [query, setQuery] = useState('');
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    THROTTLER.debounce(() => {
      const filteredData = removeEmpty(data, compact);

      const searchedData = searchObject(filteredData, query, flat);

      setResult(searchedData);
    });
  }, [compact, data, flat, query]);

  const hasError = useMemo(() => {
    try {
      new RegExp(query);

      return false;
    } catch (e) {
      return true;
    }
  }, [query]);

  const shouldCollapse = useCallback((field: CollapsedFieldProps) => {
    return (field.name !== 'root' && field.type !== 'object') || field.namespace.length > 3;
  }, []);

  const renderer = useMemo(
    () =>
      result && (
        <ReactJson
          src={result}
          theme={isDark ? 'summerfruit' : 'summerfruit:inverted'}
          indentWidth={2}
          displayDataTypes={!compact}
          displayObjectSize={!compact}
          shouldCollapse={collapse ? shouldCollapse : false}
          quotesOnKeys={false}
          style={{ flex: 1, overflow: 'auto', height: '100%', fontSize: compact ? 'small' : 'smaller' }}
          enableClipboard={_data => {
            if (typeof _data.src === 'string') {
              navigator.clipboard.writeText(_data.src);
            } else {
              navigator.clipboard.writeText(JSON.stringify(_data.src));
            }
          }}
          {...({
            // Type declaration is wrong - this is a valid prop
            displayArrayKey: !compact
          } as any)}
        />
      ),
    [collapse, compact, isDark, result, shouldCollapse]
  );

  return data ? (
    <Stack direction="column" spacing={1} sx={{ '& > div:first-of-type': { mt: 1, mr: 0.5 } }}>
      <Phrase
        value={query}
        onChange={setQuery}
        error={hasError}
        label={t('json.viewer.search.label')}
        placeholder={t('json.viewer.search.prompt')}
        disabled={!result}
        endAdornment={
          <IconButton onClick={() => setQuery('')}>
            <Clear />
          </IconButton>
        }
      />
      {renderer}
    </Stack>
  ) : (
    <Skeleton width="100%" height="95%" variant="rounded" />
  );
};

export default JSONViewer;

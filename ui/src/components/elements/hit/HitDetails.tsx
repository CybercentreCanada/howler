/* eslint-disable react/no-array-index-key */
/* eslint-disable @typescript-eslint/no-use-before-define */
import { ArrowDropDown, InfoOutlined } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Divider,
  Grid,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material';
import { flatten } from 'flat';
import Fuse from 'fuse.js';
import {
  capitalize,
  groupBy,
  isArray,
  isEmpty,
  isNull,
  isObject,
  isPlainObject,
  isUndefined,
  max,
  sortBy,
  uniq
} from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Throttler from 'utils/Throttler';

const ListRenderer: FC<{
  objKey?: string;
  maxKeyLength?: number;
  entries: any[];
}> = memo(({ objKey: key, entries, maxKeyLength }) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const allPrimitives = useMemo(() => entries.every(entry => !isObject(entry)), [entries]);
  const uniqueEntries = useMemo(() => uniq(entries), [entries]);
  const omittedDuplicates = useMemo(() => uniqueEntries.length !== entries.length, [entries, uniqueEntries]);

  return (
    <Box
      className={key.replace(/\./g, '_')}
      display={allPrimitives ? 'grid' : 'flex'}
      sx={[
        allPrimitives
          ? {
              gridTemplateColumns: '40% 60%'
            }
          : {
              flexDirection: 'column'
            }
      ]}
      overflow="hidden"
      maxWidth="100%"
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: allPrimitives ? 'end' : 'start',
          borderRight: allPrimitives ? '1px solid' : 'none',
          borderColor: theme.palette.divider,
          pr: 1,
          mr: 1
        }}
      >
        <code
          style={{
            marginTop: allPrimitives ? 0 : theme.spacing(2),
            marginBottom: allPrimitives ? 0 : theme.spacing(1)
          }}
        >
          {allPrimitives ? key.padStart(maxKeyLength ?? key.length) : key}
        </code>
      </Box>
      <Grid container spacing={allPrimitives ? 1 : 4} ml={allPrimitives ? -1 : -4} overflow="hidden" maxWidth="100%">
        {uniqueEntries.map((entry, index) => {
          if (Array.isArray(entry)) {
            return (
              <Grid item xs="auto" maxWidth="100%" key={index}>
                <ListRenderer objKey={`${key}.${index}`.replace(/\./g, '_')} entries={entry} />
              </Grid>
            );
          }

          if (isPlainObject(entry)) {
            return (
              <Grid item xs={'auto'} maxWidth="100%" minWidth="350px" key={index}>
                <ObjectRenderer parentKey={`${key}.${index}`.replace(/\./g, '_')} indent data={entry} />
              </Grid>
            );
          }

          let entryElement = <span style={{ maxWidth: '100%' }}>{entry}</span>;

          return (
            <Grid
              item
              maxWidth="100%"
              key={entry}
              className={`${key}_${index}`.replace(/\./g, '_')}
              component="code"
              display="flex"
              flexDirection="row"
            >
              {entryElement}
              {/* eslint-disable-next-line react/jsx-no-literals */}
              {allPrimitives && index < uniqueEntries.length - 1 && <span>,</span>}
            </Grid>
          );
        })}
        {omittedDuplicates && (
          <Grid item display="flex" alignItems="center">
            <Tooltip title={t('duplicates.omitted')}>
              <InfoOutlined sx={{ fontSize: '20px', ml: 1 }} color="disabled" />
            </Tooltip>
          </Grid>
        )}
      </Grid>
    </Box>
  );
});

const ObjectRenderer: FC<{ parentKey?: string; showParentKey?: boolean; data: any; indent?: boolean }> = memo(
  ({ data, parentKey, indent = false }) => {
    const theme = useTheme();

    const entries = useMemo(() => {
      const unsorted = Object.entries(flatten(data, { safe: true })).map(([key, val]) => [key, val]);

      const sortedAlphabetical = unsorted.map(([key]) => key).sort();

      return sortBy(
        unsorted,
        ([key, val]) =>
          sortedAlphabetical.indexOf(key) -
          // This pushes complex objects to the bottom of the list, so they are always rendered last.
          // We check for if the value is a primitve, or if it's an array and every entry is a primitive.
          (!isObject(val) || (isArray(val) && val.every(entry => !isObject(entry))) ? 10000 : 0)
      );
    }, [data]);

    const longestKey = useMemo(() => max(entries.map(([key]) => key.length)), [entries]);

    return (
      <Stack direction="row" overflow="hidden" maxWidth="100%">
        {indent && <Divider orientation="vertical" flexItem sx={{ borderColor: 'primary.main', borderWidth: '2px' }} />}
        <Stack flex={1} ml={1} maxWidth="100%">
          {entries
            .filter(([__, val]) => !isNull(val) && !isUndefined(val) && !isEmpty(val))
            .map(([key, val]) => {
              if (Array.isArray(val)) {
                return <ListRenderer maxKeyLength={longestKey} key={key} objKey={key} entries={val} />;
              }

              return (
                <code
                  className={(parentKey ? `${parentKey}.${key}` : key).replace(/\./g, '_')}
                  key={key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '40% 60%',
                    alignItems: 'start',
                    maxWidth: '100%'
                  }}
                >
                  <Box
                    display="flex"
                    justifyContent="end"
                    sx={{
                      marginRight: theme.spacing(1),
                      marginBottom: 0,
                      marginTop: 0,
                      borderRight: '1px solid',
                      borderColor: theme.palette.divider,
                      paddingRight: theme.spacing(1),
                      height: '100%',
                      wordWrap: 'break-word'
                    }}
                  >
                    <code style={{ maxWidth: '100%' }}>{key}</code>
                  </Box>
                  <span style={{ maxWidth: '100%' }}>{val}</span>
                </code>
              );
            })}
        </Stack>
      </Stack>
    );
  }
);

const Collapsible: FC<{ query: string; title: string; data: { [index: string]: any } }> = memo(
  ({ title, data, query }) => {
    const throttler = useMemo(() => new Throttler(400), []);

    const [scores, setScores] = useState<[string, number][]>([]);
    const [results, setResults] = useState<{ [index: string]: any }>({});

    const options = useMemo(() => Object.entries(data).map(([key, value]) => ({ key, value })), [data]);

    const keys = useMemo(
      () =>
        options
          .flatMap(option => (isArray(option.value) ? Object.keys(flatten(option.value)) : []))
          .map(key => key.replace(/\d+/g, 'value'))
          .filter(key => !!key),
      [options]
    );

    const fuse = useMemo(
      () => new Fuse(options, { includeScore: true, threshold: 0.4, keys: uniq(['key', 'value', ...keys]) }),
      [keys, options]
    );

    useEffect(() => {
      if (!query) {
        setResults(data);
        setScores([]);
        return;
      }

      throttler.debounce(() => {
        const fuseResults = fuse.search(query);
        setScores(fuseResults.map(result => [result.item.key, result.score]));
        setResults(fuseResults.reduce((acc, entry) => ({ ...acc, [entry.item.key]: entry.item.value }), {}));
      });
    }, [data, fuse, query, throttler]);

    const styles = useMemo(
      () =>
        scores.map(([key, score]) => ({
          [`& .${key.replace(/\./g, '_')}`]: {
            opacity: 1 - Math.pow(score, 0.5),
            fontWeight: score < 0.05 ? 'bold' : 'initial'
          }
        })),
      [scores]
    );

    if (isEmpty(results)) {
      return null;
    }

    return (
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ArrowDropDown />}>
          <Typography>{title}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Stack spacing={1} justifyContent="stretch" sx={styles}>
            <ObjectRenderer showParentKey data={results} />
          </Stack>
        </AccordionDetails>
      </Accordion>
    );
  }
);

const HitDetails: FC<{ hit: Hit }> = ({ hit }) => {
  const { t } = useTranslation();

  const [query, setQuery] = useState('');

  const groups = useMemo(
    () =>
      groupBy(
        Object.entries(flatten(hit ?? {}, { safe: true })).filter(
          ([key, value]) =>
            key.includes('.') && ['howler', 'labels'].every(prefix => !key.startsWith(prefix)) && !isEmpty(value)
        ),
        ([key]) => key.split('.')[0]
      ),
    [hit]
  );

  return (
    <Stack spacing={1}>
      <TextField value={query} onChange={event => setQuery(event.target.value)} label={t('overview.search')} />
      {Object.entries(groups).map(([section, entries]) => {
        return (
          <Collapsible
            query={query}
            key={section}
            title={section
              .split('_')
              .map(word => capitalize(word))
              .join(' ')}
            data={Object.fromEntries(entries)}
          />
        );
      })}
    </Stack>
  );
};

export default memo(HitDetails);

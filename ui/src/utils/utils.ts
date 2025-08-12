import * as colors from '@mui/material/colors';
import { flatten, unflatten } from 'flat';
import { isArray, isEmpty, isNil, isObject, isPlainObject } from 'lodash-es';
import moment from 'moment';

export const bytesToSize = (bytes: number | null) => {
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  if (bytes === 0 || bytes === null) return '0 B';
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${Math.round(bytes / Math.pow(1024, i))} ${sizes[i]}`;
};

export const humanReadableNumber = (num: number | null) => {
  const sizes = ['', 'k', 'm', 'g', 't', 'p', 'e', 'z', 'y'];
  if (num === 0 || num === null) return '0 ';
  const i = Math.floor(Math.log(num) / Math.log(1000));
  return `${Math.round(num / Math.pow(1000, i))}${sizes[i]} `;
};

export const getProvider = () => {
  if (window.location.pathname.indexOf(`${import.meta.env.PUBLIC_URL}/oauth/`) !== -1) {
    return window.location.pathname
      .split(`${import.meta.env.PUBLIC_URL}/oauth/`)
      .pop()
      .slice(0, -1);
  }
  const params = new URLSearchParams(window.location.search);
  return params.get('provider');
};

export const searchResultsDisplay = (count: number, max: number = 10000) => {
  const params = new URLSearchParams(window.location.search);
  const trackedHits = params.get('track_total_hits');

  if (count === parseInt(trackedHits) || (trackedHits === null && count === max)) {
    return `${count}+`;
  }

  return `${count}`;
};

const DATE_FORMAT = 'YYYY/MM/DD HH:mm:ss';
export const formatDate = (date: number | string | Date): string => {
  if (!date) {
    return '?';
  }

  return moment(date).utc().format(DATE_FORMAT);
};

export const compareTimestamp = (a: string, b: string): number => {
  return (new Date(a).getTime() - new Date(b).getTime()) / 1000;
};

export const twitterShort = (date: string | Date | number): string => {
  if (!date || date === '?') {
    return '?';
  }

  return moment(date).fromNow();
};

export const hashCode = (s: string): number => s.split('').reduce((a, b) => ((a << 5) - a + b.charCodeAt(0)) | 0, 0);

export const stringToColor = (string: string) => {
  const number = Math.abs(hashCode(string));
  const colorKeys = Object.keys(colors).filter(key => key !== 'common');

  const colorKey = colorKeys[number % colorKeys.length];
  // eslint-disable-next-line import/namespace
  const color = colors[colorKey] as { [shade: string]: string };

  const shade = Math.max(Math.floor((number / 1000) % 10), 1) * 100;

  return color[shade];
};

// Adapted from here: https://stackoverflow.com/a/48429492
export const delay = (ms: number, rejectOnCancel = false) => {
  let timerId: number;
  let onCancel: () => void;

  class TimedPromise extends Promise<void> {
    cancel = () => {
      if (rejectOnCancel) {
        onCancel();
      }

      clearTimeout(timerId);
    };
  }

  return new TimedPromise((resolve, reject) => {
    timerId = setTimeout(resolve, ms) as unknown as number;
    onCancel = reject;
  });
};

type Timestamp = {
  timestamp?: string;
};

export const sortByTimestamp = <T extends Timestamp>(arr: T[]) => {
  return (arr ?? []).slice().sort((a, b) => compareTimestamp(b.timestamp, a.timestamp));
};

export const getTimeRange = (arr: string[]): [string, string] => {
  const sorted = arr.sort((a, b) => compareTimestamp(a, b));

  return [sorted[0], sorted[sorted.length - 1]];
};

export const removeEmpty = (obj: any, aggressive = false) => {
  if (aggressive && isEmpty(obj)) {
    return null;
  } else if (isArray(obj)) {
    return obj;
  }

  return Object.fromEntries(
    Object.entries(obj ?? {})
      .filter(([__, v]) => !isNil(v))
      .map(([k, v]) => [k, isPlainObject(v) || isArray(v) ? removeEmpty(v, aggressive) : v])
      .filter(([__, v]) => !!v)
  );
};

export const searchObject = (o: any, query: string, returnFlat = false) => {
  if (!query) {
    return returnFlat ? flatten(o) : o;
  }

  try {
    const regex = new RegExp(query, 'i');

    const filteredData =
      Object.fromEntries(Object.entries(flatten(o)).filter(([k, v]) => regex.test(k) || regex.test(v))) ?? {};

    return returnFlat ? filteredData : unflatten(filteredData);
  } catch (e) {
    return returnFlat ? flatten(o) : o;
  }
};

const DATE_TO_LUCENE_MAP = {
  day: 'd',
  week: 'w',
  month: 'M',
  year: 'y'
};

export const convertDateToLucene = (date: string) => {
  if (!date.startsWith('date.range.')) {
    return '[now-1d TO now]';
  }

  if (date.endsWith('all')) {
    return '*';
  }

  const [amount, type] = date.replace('date.range.', '').split('.');

  return `[now-${amount}${DATE_TO_LUCENE_MAP[type] ?? 'd'} TO now]`;
};

export const convertCustomDateRangeToLucene = (startDate: string, endDate: string) => {
  return `[${startDate} TO ${endDate}]`;
};

export const convertLuceneToDate = (lucene: string) => {
  if (!lucene.includes(':')) {
    return lucene;
  }

  const [amount, initial] = lucene.replace(/.+\[now-(\d+)(\w+) TO now]/, '$1 $2').split(' ');

  const type = Object.entries(DATE_TO_LUCENE_MAP).find(([__, _initial]) => _initial === initial)?.[0] ?? 'day';

  return `date.range.${amount}.${type}`;
};

export const tryParse = (json: string) => {
  try {
    return JSON.parse(json);
  } catch (e) {
    return json;
  }
};

export const flattenDeep = (data: { [index: string]: any }): { [index: string]: any } => {
  const partialFlat = flatten(data, { safe: true });

  const final: { [index: string]: any } = {};
  Object.entries(partialFlat).forEach(([key, value]) => {
    if (!Array.isArray(value) || value.length === 0 || !value.some(entry => isObject(entry))) {
      final[key] = value;
    } else {
      value.forEach(entry => {
        const flattenedEntry = flattenDeep(entry);

        Object.entries(flattenedEntry).forEach(([childKey, childValue]) => {
          const fullKey = `${key}.${childKey}`;
          if (!final[fullKey]) {
            if (Array.isArray(childValue)) {
              final[fullKey] = childValue;
            } else {
              final[fullKey] = [childValue];
            }
          } else {
            if (Array.isArray(childValue)) {
              final[fullKey] = [...final[fullKey], ...childValue];
            } else {
              final[fullKey].push(childValue);
            }
          }
        });
      });
    }
  });

  return final;
};

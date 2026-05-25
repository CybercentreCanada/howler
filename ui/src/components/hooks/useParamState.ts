import { useCallback, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

type Primitive = string | number | boolean | null;

const parseValue = <T extends Primitive>(raw: string | null, defaultValue: T): T => {
  if (raw === null) return defaultValue;
  if (typeof defaultValue === 'boolean') return (raw === 'true') as unknown as T;
  if (typeof defaultValue === 'number') {
    const n = Number(raw);
    return (isNaN(n) ? defaultValue : n) as T;
  }
  return raw as unknown as T;
};

const serializeValue = (value: Primitive): string => {
  if (value === null || value === undefined) return '';
  return String(value);
};

// Scalar mode
const useParamState: {
  <T extends Primitive>(key: string, defaultValue?: T, list?: false): [T, (value: T) => void];
  // List mode
  <T extends Exclude<Primitive, null>>(key: string, defaultValue: T, list: true): [T[], (value: T[]) => void];
} = <T extends Primitive>(key: string, defaultValue: T = null as T, list = false) => {
  const [searchParams, setSearchParams] = useSearchParams();

  const [value, setValue] = useState<T | T[]>(() => {
    if (list) {
      const raws = searchParams.getAll(key);
      return raws.map(r => parseValue(r, defaultValue as Exclude<T, null>)) as T[];
    }
    return parseValue(searchParams.get(key), defaultValue);
  });

  const setter = useCallback(
    (newValue: T | T[]) => {
      setValue(newValue);
      setSearchParams(
        prev => {
          const next = new URLSearchParams(prev);
          next.delete(key);
          if (list) {
            (newValue as T[]).forEach(item => next.append(key, serializeValue(item)));
          } else {
            const scalar = newValue as T;
            if (scalar !== defaultValue && scalar !== null && scalar !== undefined) {
              next.set(key, serializeValue(scalar));
            }
          }
          return next;
        },
        { replace: true }
      );
    },
    [key, defaultValue, list, setSearchParams]
  );

  return [value, setter] as [typeof value, typeof setter];
};

export default useParamState;

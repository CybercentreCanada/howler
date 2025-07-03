import { useMemo } from 'react';

// @ts-ignore
const APP_ENV = process.env;

export default function useAppEnv(key?: string) {
  return useMemo(() => {
    if (key) {
      return APP_ENV[key];
    }
    return APP_ENV;
  }, [key]);
}

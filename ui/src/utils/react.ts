import { cloneDeep, set, type PropertyPath } from 'lodash-es';

export const setter =
  <T extends object>(path: PropertyPath, value: any) =>
  (obj: T) =>
    set(cloneDeep(obj), path, value);

import type { Overview } from './entities/generated/Overview';
import type { Template } from './entities/generated/Template';

export type WithMetadata<T> = T & {
  __template?: Template;
  __overview?: Overview;
};

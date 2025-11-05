import type { Analytic } from './entities/generated/Analytic';
import type { Dossier } from './entities/generated/Dossier';
import type { Overview } from './entities/generated/Overview';
import type { Template } from './entities/generated/Template';

export type WithMetadata<T> = T & {
  __analytic?: Analytic;
  __overview?: Overview;
  __template?: Template;

  __dossiers?: Dossier[];
};

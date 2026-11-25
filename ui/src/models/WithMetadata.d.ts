import type { Analytic } from './entities/generated/Analytic';
import type { Dossier } from './entities/generated/Dossier';
import type { Overview } from './entities/generated/Overview';
import type { Template } from './entities/generated/Template';

// Search metadata can identify a built-in template as readonly.
export type MatchedTemplate = Omit<Template, 'type'> & { type?: Template['type'] | 'readonly' };

export type WithMetadata<T> = T & {
  __index?: string;

  __analytic?: Analytic;
  __overview?: Overview;
  __template?: MatchedTemplate | null;
  __dossiers?: Dossier[];
};

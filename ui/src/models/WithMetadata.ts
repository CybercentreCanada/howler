import type { Template } from './entities/generated/Template';

export type WithMetadata<T> = T & {
  __template?: Template;
};

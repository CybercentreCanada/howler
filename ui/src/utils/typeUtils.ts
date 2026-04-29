import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import type { WithMetadata } from 'models/WithMetadata';

export const isHit = (obj: WithMetadata<any>): obj is Hit => {
  if (!obj) {
    return false;
  }

  if (obj.__index === 'hit') {
    return true;
  }

  return false;
};

export const isCase = (obj: WithMetadata<any>): obj is Case => {
  if (!obj) {
    return false;
  }

  if (obj.__index === 'case') {
    return true;
  }

  return false;
};

export const isObservable = (obj: WithMetadata<any>): obj is Observable => {
  if (!obj) {
    return false;
  }

  if (obj.__index === 'observable') {
    return true;
  }

  return false;
};

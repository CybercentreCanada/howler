import type { Case } from 'models/entities/generated/Case';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
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

export const isEvent = (obj: WithMetadata<any>): obj is Event => {
  if (!obj) {
    return false;
  }

  if (obj.__index === 'event') {
    return true;
  }

  return false;
};

/** @deprecated Use isEvent instead */
export const isObservable = isEvent;

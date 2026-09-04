import type { Hit } from 'models/entities/generated/Hit';
import hitsData from './hit.json';

type HitFixture = Omit<Hit, '__index'>;

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null;
};

const isHitFixture = (value: unknown): value is HitFixture => {
  if (!isRecord(value) || typeof value.timestamp !== 'string' || !isRecord(value.howler)) {
    return false;
  }

  const { analytic, assignment, hash, id } = value.howler;
  return [analytic, assignment, hash, id].every(field => typeof field === 'string');
};

export const getExampleHit = (): Hit => {
  const hit = Object.values(hitsData.GET)[0];
  if (!isHitFixture(hit)) {
    throw new Error('The example hit fixture is missing required Hit fields.');
  }

  return Object.assign(structuredClone(hit), { __index: 'hit' as const });
};

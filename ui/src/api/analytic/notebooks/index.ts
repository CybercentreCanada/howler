import { hdelete, hpost, joinUri } from 'api';
import { uri as parentUri } from 'api/analytic';
import type { Analytic } from 'models/entities/generated/Analytic';

export const uri = (analytic: string) => {
  return joinUri(parentUri(analytic), 'notebooks');
};

export const post = (analytic: string, body: { detection: string; value: string; name: string }): Promise<Analytic> => {
  return hpost(uri(analytic), body);
};

export const del = (analytic: string, notebooks: string[]): Promise<{ success: boolean }> => {
  return hdelete(uri(analytic), notebooks);
};

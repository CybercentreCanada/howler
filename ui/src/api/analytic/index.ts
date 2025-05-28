import { hdelete, hget, hput, joinAllUri, joinUri, uri as parentUri } from 'api';
import * as comments from 'api/analytic/comments';
import * as favourite from 'api/analytic/favourite';
import * as notebooks from 'api/analytic/notebooks';
import * as owner from 'api/analytic/owner';
import * as rules from 'api/analytic/rules';
import type { Analytic } from 'models/entities/generated/Analytic';

export type EditOptions = Pick<Analytic, 'description' | 'rule' | 'rule_crontab' | 'triage_settings'>;

export const uri = (id?: string) => {
  return id ? joinAllUri(parentUri(), 'analytic', id) : joinUri(parentUri(), 'analytic');
};

export const get = (id?: string) => {
  return id ? hget<Analytic>(uri(id)) : hget<Analytic[]>(uri());
};

export const put = (id: string, editData: EditOptions): Promise<Analytic> => {
  return hput(uri(id), editData);
};

export const del = (id: string) => {
  return hdelete(uri(id));
};

export { comments, favourite, notebooks, owner, rules };

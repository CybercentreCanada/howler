import * as ai from 'api/v2/ai';
import * as case_ from 'api/v2/case';
import * as fuzzy from 'api/v2/fuzzy';
import * as ingest from 'api/v2/ingest';
import * as search from 'api/v2/search';
import * as task from 'api/v2/task';

export const uri = () => {
  return '/api/v2';
};

export { ai, case_ as case, fuzzy, ingest, search, task };

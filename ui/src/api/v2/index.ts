import * as case_ from 'api/v2/case';
import * as fuzzy from 'api/v2/fuzzy';
import * as search from 'api/v2/search';
import * as task from 'api/v2/task';

export const uri = () => {
  return '/api/v2';
};

export { case_ as case, fuzzy, search, task };

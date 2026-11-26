import { joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2';
import * as lucene from './lucene';

export const uri = () => {
  return joinAllUri(parentUri(), 'ai');
};

export { lucene };

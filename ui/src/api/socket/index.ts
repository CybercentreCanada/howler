import { joinAllUri } from 'api';
import * as viewers from 'api/socket/viewers';

export const uri = (): string => {
  return joinAllUri('/socket', 'v1');
};

export { viewers };

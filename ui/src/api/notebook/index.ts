import { hpost, joinUri, uri as parentUri } from 'api';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';

import * as environments from 'api/notebook/environments';

export type NotebookResponse = {
  nb_content: any;
  name: string;
};

export const uri = () => {
  return joinUri(parentUri(), 'notebook');
};

export const post = (body: { link: string; analytic: Analytic; hit?: Hit }): Promise<NotebookResponse> => {
  return hpost(joinUri(uri(), 'notebook'), body);
};

export { environments };

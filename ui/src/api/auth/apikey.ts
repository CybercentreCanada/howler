import { hdelete, hpost, joinUri } from 'api';
import { uri as parentUri } from 'api/auth';

export type Privileges = 'R' | 'W' | 'E' | 'I';

type CreateApiKeyResponse = {
  apikey: string;
};

export const uri = (apiKeyName?: string) => {
  return apiKeyName ? joinUri(joinUri(parentUri(), 'apikey'), apiKeyName) : joinUri(parentUri(), 'apikey');
};

export const post = (apiKeyName: string, priv: Privileges[], expiryDate: string): Promise<CreateApiKeyResponse> => {
  return hpost(uri(), { name: apiKeyName, priv, expiry_date: expiryDate });
};

export const del = (apiKeyName: string) => {
  return hdelete(uri(apiKeyName));
};

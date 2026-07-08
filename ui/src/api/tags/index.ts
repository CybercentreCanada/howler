import { uri as apiUri, hget, joinUri } from 'api';
import type { HowlerUser } from 'models/entities/HowlerUser';

const BASE_URI = (): string => joinUri(apiUri(), 'tags');

export type UserTags = NonNullable<HowlerUser['tags']>;
export type TagCategory = keyof UserTags;
export type TagEntry = {
  name: string;
  value: string;
};
export type TagsDictionary = {
  [key in TagCategory]: TagEntry[];
};

export const getTags = (): Promise<TagsDictionary> => {
  const path = joinUri(BASE_URI(), 'all');
  return hget(path);
};

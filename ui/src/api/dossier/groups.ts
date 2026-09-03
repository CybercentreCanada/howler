import { hget, joinAllUri } from 'api';
import { uri as parentUri } from '.';

export const uri = () => joinAllUri(parentUri(), 'groups');

export const get = (prefix: string): Promise<string[]> => hget(uri(), new URLSearchParams({ prefix }));

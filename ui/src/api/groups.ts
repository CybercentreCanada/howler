import { hget, joinAllUri, uri as parentUri } from 'api';

export const uri = () => joinAllUri(parentUri(), 'groups');

export const get = (prefix: string) => hget<string[]>(uri(), new URLSearchParams({ prefix }));

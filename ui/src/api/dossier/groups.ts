import { hget, joinAllUri } from 'api';
import { uri as parentUri } from 'api/dossier';

export const uri = () => joinAllUri(parentUri(), 'groups');

export const get = (prefix: string) => hget<string[]>(uri(), new URLSearchParams({ prefix }));

import { joinAllUri } from 'api';
import { uri as parentUri } from 'api/v2/notification';
import * as user from 'api/v2/notification/get/user';

export const uri = () => joinAllUri(parentUri(), 'get');

export { user };

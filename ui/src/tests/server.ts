import { http } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from './server-handlers';

const server = setupServer(...handlers);
export { http, server };

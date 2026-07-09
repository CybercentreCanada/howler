import * as matchers from '@testing-library/jest-dom/matchers';
import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import { server } from 'tests/server';

dayjs.extend(utc);
dayjs.extend(relativeTime);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Extend vitest with the dom matchers from jest-dom.
expect.extend(matchers);

// tell React Testing Library to look for id as the testId.
configure({ testIdAttribute: 'id' });

beforeAll(() => server.listen());

afterEach(() => {
  server.resetHandlers();
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterAll(() => server.close());

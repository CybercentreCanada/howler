/// <reference types="vitest" />
import * as matchers from '@testing-library/jest-dom/matchers';
import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Extend vitest with the dom matchers from jest-dom.
expect.extend(matchers);

// tell React Testing Library to look for id as the testId.
configure({ testIdAttribute: 'id' });

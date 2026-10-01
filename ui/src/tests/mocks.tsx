import { createContext, forwardRef, useContext } from 'react';
import type { useSearchParams } from 'react-router';
import { vi, type Mock } from 'vitest';
import MockLocalStorage from './MockLocalStorage';

type SearchParamsSetter = ReturnType<typeof useSearchParams>[1];

type ReactRouterMock = {
  mockSearchParams: URLSearchParams;
  mockSetParams: Mock<SearchParamsSetter>;
  mockLocation: { pathname: string; search: string };
  mockParams: { id: string | undefined };
};

/**
 * Sets up a mock for use-context-selector that uses React's native context
 * This allows tests to use context providers without the full use-context-selector implementation
 */
export const setupContextSelectorMock = () => {
  beforeAll(() => {
    vi.mock('use-context-selector', async () => {
      const actual = await vi.importActual('use-context-selector');
      return {
        ...actual,
        createContext,
        useContextSelector: (_context: any, selector: any) => {
          return selector(useContext(_context));
        }
      };
    });
  });

  afterAll(() => vi.resetModules());
};

/**
 * Sets up a mock for react-router with common defaults
 * @param options - Override specific router behavior
 */
export const setupReactRouterMock = (): ReactRouterMock => {
  const mockLocation = vi.hoisted((): ReactRouterMock['mockLocation'] => ({ pathname: '/hits', search: '' }));
  const mockParams = vi.hoisted((): ReactRouterMock['mockParams'] => ({ id: undefined }));
  const mockSearchParams = vi.hoisted(() => new URLSearchParams());
  const mockSetParams = vi.hoisted(() => vi.fn<SearchParamsSetter>());

  beforeAll(() => {
    vi.mock('react-router', async () => {
      const actual = await vi.importActual('react-router');

      return {
        ...actual,
        Link: forwardRef<any, any>(({ to, children, ...props }, ref) => (
          <a ref={ref} href={to} {...props}>
            {children}
          </a>
        )),
        useLocation: vi.fn(() => mockLocation),
        useParams: vi.fn(() => mockParams),
        useSearchParams: vi.fn(() => [mockSearchParams, mockSetParams]),
        useNavigate: () => vi.fn()
      };
    });
  });

  afterAll(() => vi.resetModules());

  return { mockSearchParams, mockSetParams, mockLocation, mockParams };
};

/**
 * Sets up a mock localStorage instance
 */
export const setupLocalStorageMock = () => {
  const mockLocalStorage: Storage = new MockLocalStorage() as any;
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true
  });

  return mockLocalStorage;
};

/**
 * Sets up a mock sessionStorage instance
 */
export const setupSessionStorageMock = () => {
  const mockSessionStorage: Storage = new MockLocalStorage() as any;
  Object.defineProperty(window, 'sessionStorage', {
    value: mockSessionStorage,
    writable: true
  });

  return mockSessionStorage;
};

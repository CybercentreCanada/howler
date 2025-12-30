import { createContext, forwardRef, useContext } from 'react';
import { vi } from 'vitest';

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
 * Sets up a mock for react-router-dom with common defaults
 * @param options - Override specific router behavior
 */
export const setupReactRouterMock = () => {
  const mockLocation = vi.hoisted(() => ({ pathname: '/hits', search: '' }));
  const mockParams = vi.hoisted(() => ({ id: undefined }));
  const mockSearchParams = vi.hoisted(() => new URLSearchParams());
  const mockSetParams = vi.hoisted(() => vi.fn());

  beforeAll(() => {
    vi.mock('react-router-dom', () => ({
      Link: forwardRef<any, any>(({ to, children, ...props }, ref) => (
        <a ref={ref} href={to} {...props}>
          {children}
        </a>
      )),
      useLocation: vi.fn(() => mockLocation),
      useParams: vi.fn(() => mockParams),
      useSearchParams: vi.fn(() => [mockSearchParams, mockSetParams]),
      useNavigate: () => vi.fn()
    }));
  });

  afterAll(() => vi.resetModules());
};

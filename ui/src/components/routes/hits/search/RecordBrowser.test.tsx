import { fireEvent, render, screen } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockSetSelected = vi.hoisted(() => vi.fn());
const mockFetchViews = vi.hoisted(() => vi.fn());
const mockAddRecordToSelection = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', async () => {
  const actual = await vi.importActual<typeof import('@mui/material')>('@mui/material');

  return {
    ...actual,
    Drawer: ({ children, onClose }: PropsWithChildren<{ onClose: () => void }>) => (
      <div>
        <button aria-label="outside details" onClick={onClose} />
        {children}
      </div>
    ),
    useMediaQuery: () => true
  };
});

vi.mock('components/app/providers/ParameterProvider', async () => {
  const actual = await vi.importActual<typeof import('components/app/providers/ParameterProvider')>(
    'components/app/providers/ParameterProvider'
  );

  return {
    ...actual,
    default: ({ children }: PropsWithChildren) => children
  };
});

vi.mock('components/app/providers/RecordSearchProvider', async () => {
  const actual = await vi.importActual<typeof import('components/app/providers/RecordSearchProvider')>(
    'components/app/providers/RecordSearchProvider'
  );

  return {
    ...actual,
    default: ({ children }: PropsWithChildren) => children
  };
});

vi.mock('components/app/providers/GridColumnsProvider', () => ({
  default: ({ children }: PropsWithChildren) => children
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({ default: () => <div /> }));
vi.mock('components/elements/addons/layout/FlexPort', () => ({
  default: ({ children }: PropsWithChildren) => children
}));
vi.mock('components/routes/ErrorBoundary', () => ({ default: ({ children }: PropsWithChildren) => children }));
vi.mock('./InformationPane', () => ({ default: () => <div /> }));
vi.mock('./SearchPane', () => ({ default: () => <div /> }));
vi.mock('./grid/RecordGrid', () => ({ default: () => <div /> }));
vi.mock('components/elements/hit/HitSummary', () => ({ default: () => <div /> }));
vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [null]
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');

  return {
    ...actual,
    useLocation: () => ({ pathname: '/hits', search: '' }),
    useParams: () => ({})
  };
});

import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import RecordBrowser from './RecordBrowser';

const Wrapper = ({ children }: PropsWithChildren) => (
  <ParameterContext.Provider value={{ selected: 'hit-1', views: [], setSelected: mockSetSelected } as any}>
    <RecordContext.Provider value={{ selectedRecords: [], addRecordToSelection: mockAddRecordToSelection } as any}>
      <RecordSearchContext.Provider value={{ response: { items: [{ howler: { id: 'hit-1' } }] } } as any}>
        <ViewContext.Provider value={{ fetchViews: mockFetchViews } as any}>{children}</ViewContext.Provider>
      </RecordSearchContext.Provider>
    </RecordContext.Provider>
  </ParameterContext.Provider>
);

describe('RecordBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('clears the selected alert when the details are closed from outside', () => {
    render(<RecordBrowser />, { wrapper: Wrapper });

    fireEvent.click(screen.getByRole('button', { name: 'outside details' }));

    expect(mockSetSelected).toHaveBeenCalledWith(null);
  });
});

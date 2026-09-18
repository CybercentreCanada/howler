/// <reference types="vitest" />
import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockSetMenus = vi.hoisted(() => vi.fn());
const mockApplyMainMenuOperations = vi.hoisted(() => vi.fn((_menu: any, operations: any[]) => ({ id: 'root', operations })));
const mockFetchViews = vi.hoisted(() => vi.fn());

let appUserValue: any = {
  isReady: () => true,
  user: {
    favourite_views: ['view-2', 'view-1', 'view-1'],
    favourite_analytics: ['analytic-2', 'missing', 'analytic-1']
  }
};
const analyticContextToken = vi.hoisted(() => ({ name: 'analytic-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));
let analyticContextValue: any = { analytics: [], ready: false };

vi.mock('@mui/icons-material', () => ({
  QueryStats: () => <div>query-stats</div>,
  SavedSearch: () => <div>saved-search</div>
}));

vi.mock('@tui/core', () => ({
  useAppLeftNav: () => ({ setMenus: mockSetMenus }),
  useAppUser: () => appUserValue
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => `translated:${key}` })
}));

vi.mock('utils/menuUtils', () => ({
  applyMainMenuOperations: mockApplyMainMenuOperations
}));

vi.mock('./AnalyticProvider', () => ({
  AnalyticContext: analyticContextToken
}));

vi.mock('./ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('use-context-selector', async importOriginal => {
  const actual = await importOriginal<typeof import('use-context-selector')>();
  return {
    ...actual,
    useContextSelector: (context: any, selector: (ctx: any) => any) => {
      if (context === viewContextToken) {
        return selector({ fetchViews: mockFetchViews });
      }
      return selector(null);
    }
  };
});

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === analyticContextToken) {
        return analyticContextValue;
      }
      return actual.useContext(context);
    }
  };
});

import FavouriteProvider from './FavouritesProvider';

describe('FavouriteProvider', () => {
  beforeEach(() => {
    mockSetMenus.mockReset();
    mockApplyMainMenuOperations.mockReset();
    mockFetchViews.mockReset();
    analyticContextValue = {
      ready: true,
      analytics: [
        { analytic_id: 'analytic-1', name: 'One' },
        { analytic_id: 'analytic-2', name: 'Two' }
      ]
    };
    appUserValue = {
      isReady: () => true,
      user: {
        favourite_views: ['view-2', 'view-1', 'view-1'],
        favourite_analytics: ['analytic-2', 'missing', 'analytic-1']
      }
    };
  });

  it('builds favourite view and analytic menus and applies main-menu operations', async () => {
    mockFetchViews.mockResolvedValue([
      { view_id: 'view-1', title: 'Zulu', span: 'date.range.1.month' },
      { view_id: 'view-2', title: 'Alpha', sort: 'created asc', indexes: ['hit'] }
    ]);

    render(
      <FavouriteProvider>
        <div>child</div>
      </FavouriteProvider>
    );

    await waitFor(() => expect(mockSetMenus).toHaveBeenCalled());
    expect(mockFetchViews).toHaveBeenCalledWith(['view-2', 'view-1']);

    const callback = mockSetMenus.mock.calls[0][0];
    const updated = callback([{ id: 'root', items: [] }, { id: 'secondary' }]);
    expect(mockApplyMainMenuOperations).toHaveBeenCalled();
    expect(updated[0]).toEqual(
      expect.objectContaining({
        id: 'root',
        operations: expect.arrayContaining([
          { type: 'remove', targetId: 'views' },
          { type: 'remove', targetId: 'analytics' },
          expect.objectContaining({ type: 'insertRelative', anchorId: 'cases' }),
          expect.objectContaining({ type: 'insertRelative', anchorId: 'views' })
        ])
      })
    );
  });

  it('skips menu work until both the user and analytics are ready', async () => {
    appUserValue = {
      isReady: () => false,
      user: { favourite_views: ['view-1'], favourite_analytics: ['analytic-1'] }
    };
    analyticContextValue = { ready: false, analytics: [] };

    render(
      <FavouriteProvider>
        <div>child</div>
      </FavouriteProvider>
    );

    await new Promise(resolve => setTimeout(resolve, 0));
    expect(mockSetMenus).not.toHaveBeenCalled();
    expect(mockFetchViews).not.toHaveBeenCalled();
  });
});

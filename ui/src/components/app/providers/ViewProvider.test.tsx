import type { RenderHookResult } from '@testing-library/react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { hget, hpost, hput } from 'api';
import MockLocalStorage from 'tests/MockLocalStorage';
import { MOCK_RESPONSES } from 'tests/server-handlers';
import { useContextSelector } from 'use-context-selector';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';
import ViewProvider, { ViewContext, type ViewContextType } from './ViewProvider';

let mockUser = {
  favourite_views: ['favourited_view_id']
};

vi.mock('api', { spy: true });
vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => ({ pathname: '/views/searched_view_id' })),
  useParams: vi.fn(() => ({ id: 'searched_view_id' }))
}));
vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({
    user: mockUser,
    setUser: _user => (mockUser = _user)
  })
}));

const mockLocalStorage: Storage = new MockLocalStorage() as any;

// Replace localStorage in global scope
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

const Wrapper = ({ children }) => {
  return <ViewProvider>{children}</ViewProvider>;
};

beforeEach(() => {
  mockLocalStorage.clear();
});

describe('ViewContext', () => {
  it('should fetch the defaultView on initialization', async () => {
    mockLocalStorage.setItem(
      `${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.DEFAULT_VIEW}`,
      JSON.stringify('searched_view_id')
    );

    let hook = await act(async () =>
      renderHook(() => useContextSelector(ViewContext, ctx => ctx.views), { wrapper: Wrapper })
    );

    await waitFor(() => expect(hook.result.current.searched_view_id).not.toBeFalsy());

    expect(hook.result.current.searched_view_id).toEqual(MOCK_RESPONSES['/api/v1/search/view'].items[0]);
  });

  it('should allow the user to add and remove a favourite view', async () => {
    interface HookResult {
      addFavourite: ViewContextType['addFavourite'];
      removeFavourite: ViewContextType['removeFavourite'];
    }

    const hook: RenderHookResult<HookResult, any> = await act(async () => {
      return renderHook(
        () =>
          useContextSelector(ViewContext, ctx => ({
            addFavourite: ctx.addFavourite,
            removeFavourite: ctx.removeFavourite
          })),
        { wrapper: Wrapper }
      );
    });

    await hook.result.current.addFavourite('example_view_id');

    expect(mockUser.favourite_views).toEqual(['favourited_view_id', 'example_view_id']);

    await hook.result.current.removeFavourite('example_view_id');

    expect(mockUser.favourite_views).toEqual(['favourited_view_id']);
  });

  it('should allow the user to add and remove views', async () => {
    interface HookResult {
      addView: ViewContextType['addView'];
      removeView: ViewContextType['removeView'];
      views: ViewContextType['views'];
    }

    const hook: RenderHookResult<HookResult, any> = await act(async () => {
      return renderHook(
        () =>
          useContextSelector(ViewContext, ctx => ({
            addView: ctx.addView,
            removeView: ctx.removeView,
            views: ctx.views
          })),
        { wrapper: Wrapper }
      );
    });

    const result = await act(async () =>
      hook.result.current.addView({
        owner: 'user',
        settings: {
          advance_on_triage: false
        },
        view_id: 'example_created_view',
        query: 'howler.id:*',
        sort: 'event.created desc',
        title: 'Example View',
        type: 'personal',
        span: 'date.range.1.month'
      })
    );

    hook.rerender();

    expect(hook.result.current.views[result.view_id]).toEqual(result);

    await act(async () => hook.result.current.removeView(result.view_id));

    hook.rerender();

    expect(hook.result.current.views[result.view_id]).toBeFalsy();
  });

  describe('fetchViews', () => {
    let hook: RenderHookResult<ViewContextType['fetchViews'], any>;
    beforeEach(async () => {
      hook = await act(async () => {
        return renderHook(() => useContextSelector(ViewContext, ctx => ctx.fetchViews), { wrapper: Wrapper });
      });

      vi.mocked(hpost).mockClear();
      vi.mocked(hget).mockClear();
    });

    it('Should fetch all views when no ids are provided', async () => {
      const result = await act(async () => hook.result.current());

      expect(result.length).toBe(2);
      expect(result[0].view_id).toBe('example_view_id');
      expect(result[1].view_id).toBe('another_view_id');
    });

    it('Should search for specified views when ids are provided', async () => {
      const result = await act(async () => hook.result.current(['searched_view_id']));

      expect(hpost).toHaveBeenCalledOnce();
      expect(hpost).toBeCalledWith('/api/v1/search/view', { query: 'view_id:(searched_view_id)', rows: 1 });

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/search/view'].items);
    });

    it('Should search only for new views when ids are provided', async () => {
      await act(async () => hook.result.current(['searched_view_id']));

      expect(hpost).toHaveBeenCalledOnce();
      expect(hpost).toBeCalledWith('/api/v1/search/view', { query: 'view_id:(searched_view_id)', rows: 1 });

      vi.mocked(hpost).mockClear();
      await act(async () => hook.result.current(['searched_view_id', 'searched_view_id_2']));

      expect(hpost).toHaveBeenCalledOnce();
      expect(hpost).toBeCalledWith('/api/v1/search/view', { query: 'view_id:(searched_view_id_2)', rows: 1 });
    });

    it('Should provide cached instances as a response when the same views are requested', async () => {
      let result = await act(async () => hook.result.current(['searched_view_id']));

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/search/view'].items);

      result = await act(async () => hook.result.current(['searched_view_id']));

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/search/view'].items);

      expect(hpost).toHaveBeenCalledOnce();
    });
  });

  describe('getCurrentView', () => {
    let hook: RenderHookResult<ViewContextType['getCurrentView'], any>;
    beforeAll(async () => {
      hook = await act(async () => {
        return renderHook(() => useContextSelector(ViewContext, ctx => ctx.getCurrentView), { wrapper: Wrapper });
      });
    });

    it('should allow the user to fetch their current view based on the location', async () => {
      // lazy load should return nothing
      await expect(hook.result.current(true)).resolves.toBeFalsy();

      const result = await act(async () => hook.result.current());

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/search/view'].items[0]);
    });
  });

  describe('editView', () => {
    let hook: RenderHookResult<ViewContextType['editView'], any>;
    beforeAll(async () => {
      hook = await act(async () => {
        return renderHook(() => useContextSelector(ViewContext, ctx => ctx.editView), { wrapper: Wrapper });
      });
    });

    beforeEach(() => {
      vi.mocked(hput).mockClear();
      vi.mocked(hpost).mockClear();
    });

    it('should allow users to edit views', async () => {
      const result = await act(async () => hook.result.current('example_view_id', { query: 'howler.id:*' }));

      expect(hput).toHaveBeenCalledOnce();
      expect(hput).toBeCalledWith('/api/v1/view/example_view_id', { query: 'howler.id:*' });

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/view/example_view_id']);
    });
  });
});

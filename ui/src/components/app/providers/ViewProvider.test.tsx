import type { RenderHookResult } from '@testing-library/react';
import { act, renderHook } from '@testing-library/react';
import { hget, hpost, hput } from 'api';
import { MOCK_RESPONSES } from 'tests/server-handlers';
import { useContextSelector } from 'use-context-selector';
import ViewProvider, { ViewContext, type ViewContextType } from './ViewProvider';

vi.mock('api', { spy: true });
vi.mock('react-router-dom', () => ({
  useLocation: vi.fn(() => ({ pathname: '/views/example_view_id' })),
  useParams: vi.fn(() => ({ id: 'example_view_id' }))
}));
vi.mock('commons/components/app/hooks', () => ({
  useAppUser: () => ({
    user: {
      favourite_views: ['example_view_id']
    }
  })
}));

const Wrapper = ({ children }) => {
  return <ViewProvider>{children}</ViewProvider>;
};

describe('ViewContext', () => {
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

      expect(result).toEqual(MOCK_RESPONSES['/api/v1/view']);
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

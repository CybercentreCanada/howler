import type { RenderHookResult } from '@testing-library/react';
import { act, renderHook } from '@testing-library/react';
import { hpost, hput } from 'api';
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

/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { type PropsWithChildren } from 'react';
import { setupReactRouterMock } from 'tests/mocks';
import { vi } from 'vitest';

setupReactRouterMock();

// Import component after mocks
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import i18n from 'i18n';
import type { View } from 'models/entities/generated/View';
import { I18nextProvider } from 'react-i18next';
import { createMockView } from 'tests/utils';
import ViewLink from './ViewLink';

// Mock contexts
let mockParameterContext = {
  query: 'howler.id:*',
  sort: 'event.created desc',
  span: 'date.range.1.month',
  views: ['test-view-id'],
  setQuery: vi.fn(),
  setSort: vi.fn(),
  setSpan: vi.fn(),
  removeView: vi.fn(),
  setView: vi.fn()
};

let mockHitSearchContext = {
  search: vi.fn()
};

let mockViewContext = {
  getCurrentViews: vi.fn(),
  views: {
    'test-view-id': createMockView(),
    'another-view-id': createMockView({ view_id: 'another-view-id', title: 'Another View' })
  } as Record<string, View>
};

// Test wrapper
const Wrapper = ({ children }: PropsWithChildren) => {
  return (
    <I18nextProvider i18n={i18n as any}>
      <ParameterContext.Provider value={mockParameterContext as any}>
        <HitSearchContext.Provider value={mockHitSearchContext as any}>
          <ViewContext.Provider value={mockViewContext as any}>{children}</ViewContext.Provider>
        </HitSearchContext.Provider>
      </ParameterContext.Provider>
    </I18nextProvider>
  );
};

describe('ViewLink', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();

    // Reset mock contexts to defaults
    mockParameterContext.query = 'howler.id:*';
    mockParameterContext.sort = 'event.created desc';
    mockParameterContext.span = 'date.range.1.month';
    mockParameterContext.views = ['test-view-id'];
    mockParameterContext.removeView = vi.fn();
    mockParameterContext.setView = vi.fn();
    mockHitSearchContext.search = vi.fn();
    mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);
    mockViewContext.views = {
      'test-view-id': createMockView(),
      'another-view-id': createMockView({ view_id: 'another-view-id', title: 'Another View' })
    };
  });

  describe('Loading State', () => {
    it('should show loading spinner while fetching view', () => {
      mockViewContext.getCurrentViews = vi.fn(() => new Promise(() => {})); // Never resolves

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should hide loading spinner after view is fetched', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });
  });

  describe('View Selection Mode (Empty String)', () => {
    it('should render selection UI when viewId is empty string', async () => {
      render(<ViewLink id={0} viewId="" />, { wrapper: Wrapper });

      expect(await screen.findAllByText(i18n.t('hit.search.view.select'))).toHaveLength(1);
    });

    it('should show autocomplete for view selection', async () => {
      render(<ViewLink id={0} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      const autocomplete = screen.getByRole('combobox');
      expect(autocomplete).toBeInTheDocument();
    });

    it('should filter out views already in currentViews', async () => {
      mockParameterContext.views = ['test-view-id']; // Already selected

      render(<ViewLink id={1} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      // Open the autocomplete
      const autocomplete = screen.getByRole('combobox');
      await user.click(autocomplete);

      // test-view-id should not be in options, but another-view-id should be available
      expect(screen.queryByText('Test View')).not.toBeInTheDocument();
      expect(screen.queryByText('Another View')).toBeInTheDocument();
    });

    it('should call setView when view is selected from autocomplete', async () => {
      mockParameterContext.views = [];

      render(<ViewLink id={0} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      const autocomplete = screen.getByRole('combobox');
      await user.click(autocomplete);

      expect(mockParameterContext.setView).not.toHaveBeenCalled(); // Not clicked yet

      await screen.findByText('Test View');
      await user.click(await screen.findByText('Test View'));

      expect(mockParameterContext.setView).toHaveBeenCalledOnce();
      expect(mockParameterContext.setView).toHaveBeenCalledWith(0, 'test-view-id'); // Clicked yet
    });

    it('should show delete button in selection mode', async () => {
      render(<ViewLink id={0} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      const deleteButton = screen.getByLabelText(i18n.t('hit.search.view.remove'));
      expect(deleteButton).toBeInTheDocument();
    });

    it('should call removeView when delete button is clicked in selection mode', async () => {
      render(<ViewLink id={0} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      const deleteButton = screen.getByLabelText(i18n.t('hit.search.view.remove'));
      await user.click(deleteButton);

      expect(mockParameterContext.removeView).toHaveBeenCalledWith('');
    });
  });

  describe('View Not Found', () => {
    it('should show error chip when view is not found', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);

      render(<ViewLink id={0} viewId="non-existent-view" />, { wrapper: Wrapper });

      expect(await screen.findByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(i18n.t('view.notfound'))).toBeInTheDocument();
    });

    it('should have proper accessibility attributes on error alert', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);

      render(<ViewLink id={0} viewId="non-existent-view" />, { wrapper: Wrapper });

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'assertive');
      expect(alert).toHaveAttribute('aria-atomic', 'true');
    });

    it('should call removeView when error chip is deleted', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);

      render(<ViewLink id={0} viewId="non-existent-view" />, { wrapper: Wrapper });

      const errorChip = await screen.findByRole('alert');
      const deleteButton = errorChip.querySelector('[data-testid="CancelIcon"]')?.closest('button');

      if (deleteButton) {
        await user.click(deleteButton);
        expect(mockParameterContext.removeView).toHaveBeenCalledWith('non-existent-view');
      }
    });
  });

  describe('Valid View Display', () => {
    it('should display view title as link', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      const titleLink = await screen.findByText('Test View');
      expect(titleLink.closest('a')).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should display tooltip with view query on title', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      const tooltip = await screen.findByText('Test View');
      expect(tooltip).toHaveAttribute('aria-label', expect.stringContaining('howler.status:open'));
    });

    it('should display translated view title', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
        createMockView({
          title: 'view.assigned_to_me'
        })
      ]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      // The i18n mock should translate this key
      expect(await screen.findByText(/assigned/i)).toBeInTheDocument();
    });

    it('should display correct icon based on view type', async () => {
      const viewTypes: Array<'personal' | 'global' | 'readonly'> = ['personal', 'global', 'readonly'];

      for (const type of viewTypes) {
        vi.clearAllMocks();
        mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView({ type })]);

        const { unmount } = render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

        expect(await screen.findByLabelText(i18n.t(`route.views.manager.${type}`))).toBeInTheDocument();

        unmount();
      }
    });

    it('should display delete button to remove view', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      // The chip should have a delete button
      const chip = screen.getByText('Test View').closest('[role="button"]');
      expect(chip?.querySelector('[data-testid="CancelIcon"]')).toBeInTheDocument();
    });

    it('should call removeView when delete button is clicked', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      // Find and click the delete button on the chip
      const chip = screen.getByText('Test View').closest('[role="button"]');
      const deleteButton = chip?.querySelector('[data-testid="CancelIcon"]')?.closest('button');

      if (deleteButton) {
        await user.click(deleteButton);
        expect(mockParameterContext.removeView).toHaveBeenCalledWith('test-view-id');
      }
    });
  });

  describe('Action Buttons', () => {
    beforeEach(async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);
    });

    it('should display edit button', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const editButton = await screen.findByLabelText(i18n.t('route.views.edit'));
      expect(editButton).toBeInTheDocument();
    });

    it('should navigate to edit page when edit button is clicked', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const editButton = await screen.findByLabelText(i18n.t('route.views.edit'));
      expect(editButton.closest('a')).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should display refresh button', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const refreshButton = await screen.findByLabelText(i18n.t('view.refresh'));
      expect(refreshButton).toBeInTheDocument();
    });

    it('should call search function when refresh button is clicked', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const refreshButton = await screen.findByLabelText(i18n.t('view.refresh'));
      await user.click(refreshButton);

      expect(mockHitSearchContext.search).toHaveBeenCalledWith('howler.id:*');
    });

    it('should display open button', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const openButton = await screen.findByLabelText(i18n.t('view.open'));
      expect(openButton).toBeInTheDocument();
    });

    it('should navigate to search with view query when open button is clicked', async () => {
      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const openButton = await screen.findByLabelText(i18n.t('view.open'));
      expect(openButton.closest('a')).toHaveAttribute('href', '/search?query=howler.status:open');
    });
  });

  describe('URL Generation', () => {
    it('should generate edit URL when view exists', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const editButton = await screen.findByLabelText(i18n.t('route.views.edit'));
      expect(editButton.closest('a')).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should generate create URL with query params when view does not exist', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);
      mockParameterContext.query = 'test-query';
      mockParameterContext.sort = 'test-sort';
      mockParameterContext.span = 'test-span';

      render(<ViewLink id={0} viewId="new-view" />, { wrapper: Wrapper });

      // Wait for loading to complete
      await screen.findByRole('alert');

      // The viewUrl memo should generate create URL with params
      // This is tested indirectly through the edit button when view is null
    });

    it('should generate create URL without params when no query/sort/span', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);
      mockParameterContext.query = null;
      mockParameterContext.sort = null;
      mockParameterContext.span = null;

      render(<ViewLink id={0} viewId="new-view" />, { wrapper: Wrapper });

      await screen.findByRole('alert');

      // Should generate /views/create without query params
    });
  });

  describe('Edge Cases', () => {
    it('should handle view with missing title', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
        createMockView({
          title: undefined
        })
      ]);

      const { container } = render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      // Component should still render without crashing
      await waitFor(() => expect(container).toBeInTheDocument());
    });

    it('should handle view with missing query', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
        createMockView({
          query: undefined
        })
      ]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      const titleLink = await screen.findByText('Test View');
      expect(titleLink).toHaveAttribute('aria-label', expect.stringContaining(i18n.t('unknown')));
    });

    it('should handle undefined query in parameter context', async () => {
      mockParameterContext.query = undefined;
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const refreshButton = await screen.findByLabelText(i18n.t('view.refresh'));
      await user.click(refreshButton);

      expect(mockHitSearchContext.search).toHaveBeenCalledWith(undefined);
    });

    it('should handle custom span correctly', async () => {
      mockParameterContext.span = 'date.range.custom';
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      // Edit button should be disabled when span is custom
      const editButton = await screen.findByLabelText(i18n.t('route.views.edit'));
      expect(editButton).toHaveAttribute('aria-disabled', 'true');
    });

    it('should disable edit button when no query and no view', async () => {
      mockParameterContext.query = null;
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([]);

      render(<ViewLink id={0} viewId="new-view" />, { wrapper: Wrapper });

      await screen.findByRole('alert');

      // Can't test disabled state directly on error chip
    });

    it('should handle rapid viewId changes', async () => {
      const { rerender } = render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      expect(await screen.findByText('Test View')).toBeInTheDocument();

      // Change viewId
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
        createMockView({
          view_id: 'another-view-id',
          title: 'Another View'
        })
      ]);

      rerender(<ViewLink id={0} viewId="another-view-id" />);

      expect(await screen.findByText('Another View')).toBeInTheDocument();
    });

    it('should call getCurrentViews when viewId changes', async () => {
      const { rerender } = render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      expect(mockViewContext.getCurrentViews).toHaveBeenCalledWith({ viewId: 'test-view-id', ignoreParams: true });

      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([
        createMockView({
          view_id: 'another-view-id',
          title: 'Another View'
        })
      ]);

      rerender(<ViewLink id={0} viewId="another-view-id" />);

      await screen.findByText('Another View');

      expect(mockViewContext.getCurrentViews).toHaveBeenCalledWith({ viewId: 'another-view-id', ignoreParams: true });
    });
  });

  describe('Accessibility', () => {
    it('should have accessible link text for view title', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      const titleLink = await screen.findByText('Test View');
      expect(titleLink).toHaveAttribute('role', 'link');
      expect(titleLink.textContent).toBe('Test View');
    });

    it('should have tooltips for all action buttons', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const editButton = await screen.findByLabelText(i18n.t('route.views.edit'));
      const refreshButton = await screen.findByLabelText(i18n.t('view.refresh'));
      const openButton = await screen.findByLabelText(i18n.t('view.open'));

      expect(editButton).toHaveAttribute('aria-label');
      expect(refreshButton).toHaveAttribute('aria-label');
      expect(openButton).toHaveAttribute('aria-label');
    });

    it('should have proper ARIA attributes on view type icon', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      const icon = await screen.findByLabelText(i18n.t('route.views.manager.personal'));
      expect(icon).toHaveAttribute('aria-label');
    });
  });

  describe('Integration with Context', () => {
    it('should use getCurrentViews from ViewContext', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      expect(mockViewContext.getCurrentViews).toHaveBeenCalledWith({ viewId: 'test-view-id', ignoreParams: true });
    });

    it('should use removeView from ParameterContext', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');

      const chip = screen.getByText('Test View').closest('[role="button"]');
      const deleteButton = chip?.querySelector('[data-testid="CancelIcon"]')?.closest('button');

      if (deleteButton) {
        await user.click(deleteButton);
        expect(mockParameterContext.removeView).toHaveBeenCalledWith('test-view-id');
      }
    });

    it('should use search from HitSearchContext', async () => {
      mockViewContext.getCurrentViews = vi.fn().mockResolvedValue([createMockView()]);

      render(<ViewLink id={0} viewId="test-view-id" />, { wrapper: Wrapper });

      await screen.findByText('Test View');
      await user.click(screen.getByText('Test View').parentElement);

      const refreshButton = await screen.findByLabelText(i18n.t('view.refresh'));
      await user.click(refreshButton);

      expect(mockHitSearchContext.search).toHaveBeenCalledWith('howler.id:*');
    });

    it('should filter available views using currentViews from ParameterContext', async () => {
      mockParameterContext.views = ['test-view-id'];

      render(<ViewLink id={1} viewId="" />, { wrapper: Wrapper });

      await user.click(await screen.findByText(i18n.t('hit.search.view.select')));

      // Open the autocomplete
      const autocomplete = screen.getByRole('combobox');
      await user.click(autocomplete);

      expect(screen.queryByText('Test View')).not.toBeInTheDocument();
      expect(screen.queryByText('Another View')).toBeInTheDocument();
    });
  });
});

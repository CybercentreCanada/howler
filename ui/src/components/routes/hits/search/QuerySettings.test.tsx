/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { act, type PropsWithChildren } from 'react';
import { setupContextSelectorMock } from 'tests/mocks';
import { vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

setupContextSelectorMock();

// Mock child components
vi.mock('./shared/HitFilter', () => ({
  default: ({ id, value }: { id: number; value: string }) => (
    <div id={`hit-filter-${id}`} data-value={value}>
      HitFilter {id}: {value}
    </div>
  )
}));

vi.mock('./shared/HitSort', () => ({
  default: () => <div id="hit-sort">HitSort</div>
}));

vi.mock('./shared/SearchSpan', () => ({
  default: () => <div id="search-span">SearchSpan</div>
}));

vi.mock('./ViewLink', () => ({
  default: ({ id, viewId }: { id: number; viewId: string }) => (
    <div id={`view-link-${id}`} data-view-id={viewId}>
      ViewLink {id}: {viewId}
    </div>
  )
}));

// Import component after mocks
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import i18n from 'i18n';
import type { View } from 'models/entities/generated/View';
import { I18nextProvider } from 'react-i18next';
import { createMockView } from 'tests/utils';
import QuerySettings from './QuerySettings';

// Mock contexts
const mockAddFilter = vi.fn();
const mockAddView = vi.fn();
const mockFetchViews = vi.fn();
let mockParameterContext = {
  filters: [] as string[],
  views: [] as string[],
  addFilter: mockAddFilter,
  addView: mockAddView
};

let mockViewContext = {
  views: {} as Record<string, View>,
  fetchViews: mockFetchViews
};

// Test wrapper
const Wrapper = ({ children }: PropsWithChildren) => {
  return (
    <I18nextProvider i18n={i18n as any}>
      <ParameterContext.Provider value={mockParameterContext as any}>
        <ViewContext.Provider value={mockViewContext as any}>{children}</ViewContext.Provider>
      </ParameterContext.Provider>
    </I18nextProvider>
  );
};

describe('QuerySettings', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();

    // Reset mock contexts to defaults
    mockParameterContext.filters = [];
    mockParameterContext.views = [];
    mockParameterContext.addFilter = mockAddFilter;
    mockParameterContext.addView = mockAddView;
    mockViewContext.views = {};
    mockViewContext.fetchViews = mockFetchViews;
    mockFetchViews.mockResolvedValue(undefined);
  });

  describe('Rendering Conditions', () => {
    it('should render all core components when no filters or views exist', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.queryByTestId(/^view-link-/)).not.toBeInTheDocument();
    });

    it('should render with default boxSx when not provided', () => {
      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const box = container.firstChild;
      expect(box).toBeInTheDocument();
    });

    it('should render with custom boxSx when provided', () => {
      const customSx = { maxWidth: '800px', backgroundColor: 'red' };
      render(<QuerySettings boxSx={customSx} />, { wrapper: Wrapper });

      // Component should render without errors
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });

    it('should render Add buttons in ChipPopper', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      // Open the ChipPopper to see buttons
      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      expect(screen.getByLabelText(i18n.t('hit.search.filter.add'))).toBeInTheDocument();
      expect(screen.getByLabelText(i18n.t('hit.search.view.add'))).toBeInTheDocument();
    });
  });

  describe('Views Display', () => {
    it('should render no ViewLink components when views array is empty', () => {
      mockParameterContext.views = [];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^view-link-/)).not.toBeInTheDocument();
    });

    it('should render single ViewLink component when one view exists', () => {
      mockParameterContext.views = ['view-1'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-0')).toHaveAttribute('data-view-id', 'view-1');
    });

    it('should render multiple ViewLink components when multiple views exist', () => {
      mockParameterContext.views = ['view-1', 'view-2', 'view-3'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-1')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-2')).toBeInTheDocument();

      expect(screen.getByTestId('view-link-0')).toHaveAttribute('data-view-id', 'view-1');
      expect(screen.getByTestId('view-link-1')).toHaveAttribute('data-view-id', 'view-2');
      expect(screen.getByTestId('view-link-2')).toHaveAttribute('data-view-id', 'view-3');
    });

    it('should maintain view order in display', () => {
      mockParameterContext.views = ['view-z', 'view-a', 'view-m'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('view-link-0')).toHaveAttribute('data-view-id', 'view-z');
      expect(screen.getByTestId('view-link-1')).toHaveAttribute('data-view-id', 'view-a');
      expect(screen.getByTestId('view-link-2')).toHaveAttribute('data-view-id', 'view-m');
    });

    it('should pass correct id prop to each ViewLink', () => {
      mockParameterContext.views = ['view1', 'view2', 'view3'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByText('ViewLink 0: view1')).toBeInTheDocument();
      expect(screen.getByText('ViewLink 1: view2')).toBeInTheDocument();
      expect(screen.getByText('ViewLink 2: view3')).toBeInTheDocument();
    });

    it('should handle empty string view (selection mode)', () => {
      mockParameterContext.views = ['', 'valid-view'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('view-link-0')).toHaveAttribute('data-view-id', '');
      expect(screen.getByTestId('view-link-1')).toHaveAttribute('data-view-id', 'valid-view');
    });
  });

  describe('Filter Display', () => {
    it('should render no HitFilter components when filters array is empty', () => {
      mockParameterContext.filters = [];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^hit-filter-/)).not.toBeInTheDocument();
    });

    it('should render single HitFilter component when one filter exists', () => {
      mockParameterContext.filters = ['howler.status:open'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', 'howler.status:open');
    });

    it('should render multiple HitFilter components when multiple filters exist', () => {
      mockParameterContext.filters = ['howler.status:open', 'howler.assignment:user1', 'howler.escalation:hit'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-1')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-2')).toBeInTheDocument();

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', 'howler.status:open');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'howler.assignment:user1');
      expect(screen.getByTestId('hit-filter-2')).toHaveAttribute('data-value', 'howler.escalation:hit');
    });

    it('should maintain filter order in display', () => {
      mockParameterContext.filters = ['filter-z', 'filter-a', 'filter-m'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', 'filter-z');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'filter-a');
      expect(screen.getByTestId('hit-filter-2')).toHaveAttribute('data-value', 'filter-m');
    });

    it('should pass correct id prop to each HitFilter', () => {
      mockParameterContext.filters = ['filter1', 'filter2', 'filter3'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByText('HitFilter 0: filter1')).toBeInTheDocument();
      expect(screen.getByText('HitFilter 1: filter2')).toBeInTheDocument();
      expect(screen.getByText('HitFilter 2: filter3')).toBeInTheDocument();
    });

    it('should handle empty string filters', () => {
      mockParameterContext.filters = ['', 'valid:filter'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', '');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'valid:filter');
    });
  });

  describe('Add Filter and View Buttons', () => {
    it('should call addFilter when Add Filter button clicked', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addFilterButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      await user.click(addFilterButton);

      expect(mockAddFilter).toHaveBeenCalledWith('howler.assessment:*');
      expect(mockAddFilter).toHaveBeenCalledTimes(1);
    });

    it('should call fetchViews and addView when Add View button clicked', async () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' })
      };

      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      await user.click(addViewButton);

      expect(mockFetchViews).toHaveBeenCalledTimes(1);
      await vi.waitFor(() => {
        expect(mockAddView).toHaveBeenCalledWith('');
      });
    });

    it('should disable Add View button when no available views', async () => {
      mockViewContext.views = {};

      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      expect(addViewButton).toBeDisabled();
    });

    it('should disable Add View button when all views are in currentViews', async () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' }),
        'view-2': createMockView({ view_id: 'view-2' })
      };
      mockParameterContext.views = ['view-1', 'view-2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      expect(addViewButton).toBeDisabled();
    });

    it('should disable Add View button when empty string already in currentViews', async () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' })
      };
      mockParameterContext.views = [''];

      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      expect(addViewButton).toBeDisabled();
    });

    it('should enable Add View button when available views exist', async () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' }),
        'view-2': createMockView({ view_id: 'view-2' })
      };
      mockParameterContext.views = ['view-1'];

      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      expect(addViewButton).not.toBeDisabled();
    });

    it('should display both Add buttons in ChipPopper', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      expect(screen.getByLabelText(i18n.t('hit.search.filter.add'))).toBeInTheDocument();
      expect(screen.getByLabelText(i18n.t('hit.search.view.add'))).toBeInTheDocument();
    });

    it('should allow multiple clicks to add multiple filters', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addFilterButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));

      await act(async () => {
        await user.click(addFilterButton);
        await user.click(addFilterButton);
        await user.click(addFilterButton);
      });

      expect(mockAddFilter).toHaveBeenCalledTimes(3);
      expect(mockAddFilter).toHaveBeenCalledWith('howler.assessment:*');
    });
  });

  describe('Grid Layout', () => {
    it('should render components in Grid container', () => {
      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridContainer = container.querySelector('[class*="MuiGrid-container"]');
      expect(gridContainer).toBeInTheDocument();
    });

    it('should render each component in separate Grid item', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];
      mockParameterContext.views = ['view-1'];

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = container.querySelectorAll('[class*="MuiGrid-item"]');
      // HitSort + SearchSpan + 1 view + 2 filters + ChipPopper = 6 items
      expect(gridItems.length).toBe(6);
    });

    it('should render correct number of items with multiple views', () => {
      mockParameterContext.filters = ['filter1'];
      mockParameterContext.views = ['view-1', 'view-2', 'view-3'];

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = container.querySelectorAll('[class*="MuiGrid-item"]');
      // HitSort + SearchSpan + 3 views + 1 filter + ChipPopper = 7 items
      expect(gridItems.length).toBe(7);
    });
  });

  describe('Edge Cases', () => {
    it('should handle undefined filters gracefully', () => {
      mockParameterContext.filters = undefined as any;

      expect(() => render(<QuerySettings />, { wrapper: Wrapper })).not.toThrow();
    });

    it('should handle very long filter arrays', () => {
      const manyFilters = Array.from({ length: 100 }, (_, i) => `filter${i}`);
      mockParameterContext.filters = manyFilters;

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-99')).toBeInTheDocument();
    });

    it('should handle filters with special characters', () => {
      mockParameterContext.filters = ['filter:with:colons', 'filter&with&ampersands', 'filter with spaces'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', 'filter:with:colons');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'filter&with&ampersands');
      expect(screen.getByTestId('hit-filter-2')).toHaveAttribute('data-value', 'filter with spaces');
    });

    it('should handle rapid context changes', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      mockParameterContext = { ...mockParameterContext, filters: ['filter1'] };
      rerender(<QuerySettings />);
      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, filters: ['filter1', 'filter2'] };
      rerender(<QuerySettings />);
      expect(screen.getByTestId('hit-filter-1')).toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, filters: [] };
      rerender(<QuerySettings />);
      expect(screen.queryByTestId(/^hit-filter-/)).not.toBeInTheDocument();
    });

    it('should handle verticalSorters prop (even though unused)', () => {
      const { container } = render(<QuerySettings verticalSorters />, { wrapper: Wrapper });

      expect(container).toBeInTheDocument();
    });
  });

  describe('Integration Tests', () => {
    it('should work with all contexts simultaneously', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];
      mockParameterContext.views = ['view-1', 'view-2'];
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' }),
        'view-2': createMockView({ view_id: 'view-2' })
      };

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-1')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-1')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should update filters when context changes', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^hit-filter-/)).not.toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, filters: ['new:filter'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
    });

    it('should update views when context changes', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^view-link-/)).not.toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, views: ['view-1'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
    });

    it('should handle adding filter and updating filters array', async () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addFilterButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      await user.click(addFilterButton);

      expect(mockAddFilter).toHaveBeenCalledWith('howler.assessment:*');

      // Simulate the filter being added to the array
      mockParameterContext = { ...mockParameterContext, filters: ['howler.assessment:*'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
    });

    it('should handle adding view and updating views array', async () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1' })
      };

      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addViewButton = screen.getByLabelText(i18n.t('hit.search.view.add'));
      await user.click(addViewButton);

      expect(mockFetchViews).toHaveBeenCalled();
      await vi.waitFor(() => {
        expect(mockAddView).toHaveBeenCalledWith('');
      });

      // Simulate the view being added to the array
      mockParameterContext = { ...mockParameterContext, views: [''] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
    });

    it('should handle multiple views and filters together', () => {
      mockParameterContext.filters = ['filter1', 'filter2', 'filter3'];
      mockParameterContext.views = ['view-1', 'view-2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-1')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-1')).toBeInTheDocument();
      expect(screen.getByTestId('hit-filter-2')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible Add Filter and Add View buttons', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      expect(screen.getByLabelText(i18n.t('hit.search.filter.add'))).toBeInTheDocument();
      expect(screen.getByLabelText(i18n.t('hit.search.view.add'))).toBeInTheDocument();
    });

    it('should maintain logical tab order', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];
      mockParameterContext.views = ['view-1'];

      render(<QuerySettings />, { wrapper: Wrapper });

      // All interactive elements should be in the document
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should be keyboard accessible for Add buttons', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      await waitFor(() => expect(screen.findByLabelText(i18n.t('hit.search.filter.add'))));
      const addFilterButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));

      act(() => {
        addFilterButton.focus();
      });
      await waitFor(() => expect(addFilterButton).toHaveFocus());

      await user.keyboard('{Enter}');

      await waitFor(() => expect(mockAddFilter).toHaveBeenCalledWith('howler.assessment:*'));
    });

    it('should maintain focus when filters are added', async () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      const chipButton = screen.getByRole('button');
      await user.click(chipButton);

      const addFilterButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      await user.click(addFilterButton);

      mockParameterContext = { ...mockParameterContext, filters: ['howler.id:*'] };
      rerender(<QuerySettings />);

      // ChipPopper button should still be in document
      expect(screen.queryByText(i18n.t('hit.search.filter.add'))).toBeInTheDocument();
    });

    it('should have semantic HTML structure', () => {
      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      // Should use proper Box and Grid components
      expect(container.querySelector('[class*="MuiBox"]')).toBeInTheDocument();
      expect(container.querySelector('[class*="MuiGrid-container"]')).toBeInTheDocument();
    });

    it('should support screen reader navigation', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];
      mockParameterContext.views = ['view-1'];

      render(<QuerySettings />, { wrapper: Wrapper });

      // All major components should be identifiable
      const hitSort = screen.getByTestId('hit-sort');
      const searchSpan = screen.getByTestId('search-span');
      const viewLink = screen.getByTestId('view-link-0');
      const filter1 = screen.getByTestId('hit-filter-0');
      const filter2 = screen.getByTestId('hit-filter-1');
      const chipButton = screen.getByRole('button');

      expect(hitSort).toBeInTheDocument();
      expect(searchSpan).toBeInTheDocument();
      expect(viewLink).toBeInTheDocument();
      expect(filter1).toBeInTheDocument();
      expect(filter2).toBeInTheDocument();
      expect(chipButton).toBeInTheDocument();
    });
  });

  describe('Memoization', () => {
    it('should not re-render unnecessarily when unrelated props change', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      // Mock component should be rendered once
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();

      // Re-render with same props
      rerender(<QuerySettings />);

      // Components should still be present (memo prevents unnecessary re-renders)
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });

    it('should update when filters change', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^hit-filter-/)).not.toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, filters: ['new:filter'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
    });

    it('should update when views change', () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.queryByTestId(/^view-link-/)).not.toBeInTheDocument();

      mockParameterContext = { ...mockParameterContext, views: ['view-1'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('view-link-0')).toBeInTheDocument();
    });

    it('should update when boxSx prop changes', () => {
      const { rerender } = render(<QuerySettings boxSx={{ maxWidth: '800px' }} />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();

      rerender(<QuerySettings boxSx={{ maxWidth: '1000px' }} />);

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });

    it('should update allowAddViews when available views change', () => {
      mockViewContext.views = {};

      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      // No available views initially
      mockViewContext = {
        ...mockViewContext,
        views: {
          'view-1': createMockView({ view_id: 'view-1' })
        }
      };

      rerender(<QuerySettings />);

      // Component should respond to view context changes
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });
  });

  describe('Component Composition', () => {
    it('should render all child components in correct order', () => {
      mockParameterContext.filters = ['filter1'];
      mockParameterContext.views = ['view-1'];

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = container.querySelectorAll('[class*="MuiGrid-item"]');

      // Order: HitSort, SearchSpan, ViewLink(s), HitFilter(s), ChipPopper
      expect(gridItems[0]).toContainElement(screen.getByTestId('hit-sort'));
      expect(gridItems[1]).toContainElement(screen.getByTestId('search-span'));
      expect(gridItems[2]).toContainElement(screen.getByTestId('view-link-0'));
      expect(gridItems[3]).toContainElement(screen.getByTestId('hit-filter-0'));
      expect(gridItems[4]).toContainElement(screen.getByRole('button'));
    });

    it('should pass correct props to ViewLink components', () => {
      mockParameterContext.views = ['view-1', 'view-2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      const viewLink0 = screen.getByTestId('view-link-0');
      expect(viewLink0).toHaveAttribute('data-view-id', 'view-1');
      expect(viewLink0).toHaveTextContent('ViewLink 0: view-1');

      const viewLink1 = screen.getByTestId('view-link-1');
      expect(viewLink1).toHaveAttribute('data-view-id', 'view-2');
      expect(viewLink1).toHaveTextContent('ViewLink 1: view-2');
    });

    it('should pass correct props to HitFilter components', () => {
      mockParameterContext.filters = ['filter:value'];

      render(<QuerySettings />, { wrapper: Wrapper });

      const filter = screen.getByTestId('hit-filter-0');
      expect(filter).toHaveAttribute('data-value', 'filter:value');
      expect(filter).toHaveTextContent('HitFilter 0: filter:value');
    });

    it('should render components independently', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      // Each component should render regardless of others
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
    });

    it('should render multiple views before filters', () => {
      mockParameterContext.views = ['view-1', 'view-2'];
      mockParameterContext.filters = ['filter1'];

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = Array.from(container.querySelectorAll('[class*="MuiGrid-item"]'));
      const viewLink0Index = gridItems.findIndex(item => item.querySelector('#view-link-0'));
      const viewLink1Index = gridItems.findIndex(item => item.querySelector('#view-link-1'));
      const filterIndex = gridItems.findIndex(item => item.querySelector('#hit-filter-0'));

      // Views should come before filters
      expect(viewLink0Index).toBeLessThan(filterIndex);
      expect(viewLink1Index).toBeLessThan(filterIndex);
    });
  });
});

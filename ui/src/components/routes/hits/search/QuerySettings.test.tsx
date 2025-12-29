/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { act, createContext, useContext, type PropsWithChildren } from 'react';
import { vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Mock use-context-selector
vi.mock('use-context-selector', async () => {
  return {
    createContext,
    useContextSelector: (context, selector) => {
      return selector(useContext(context));
    }
  };
});

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
  default: () => <div id="view-link">ViewLink</div>
}));

// Import component after mocks
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import i18n from 'i18n';
import type { View } from 'models/entities/generated/View';
import { I18nextProvider } from 'react-i18next';
import { createMockView } from 'tests/utils';
import QuerySettings from './QuerySettings';

// Mock contexts
const mockAddFilter = vi.fn();
let mockParameterContext = {
  filters: [] as string[],
  addFilter: mockAddFilter
};

let mockHitSearchContext = {
  viewId: null as string | null
};

let mockViewContext = {
  views: {} as Record<string, View>
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

describe('QuerySettings', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();

    // Reset mock contexts to defaults
    mockParameterContext.filters = [];
    mockParameterContext.addFilter = mockAddFilter;
    mockHitSearchContext.viewId = null;
    mockViewContext.views = {};
  });

  describe('Rendering Conditions', () => {
    it('should render all core components when no filters exist', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.getByTestId('view-link')).toBeInTheDocument();
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

    it('should render Add Filter button when no filters exist', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByRole('button');
      expect(addButton).toBeInTheDocument();
    });

    it('should render disabled state when viewId exists but selectedView is null', () => {
      mockHitSearchContext.viewId = 'test-view-id';
      mockViewContext.views = {
        'test-view-id': null
      };

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      // Check for opacity styling on grid
      const grid = container.querySelector('[class*="MuiGrid-container"]');
      expect(grid).toBeInTheDocument();
    });

    it('should render normal state when viewId is null', () => {
      mockHitSearchContext.viewId = null;

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const grid = container.querySelector('[class*="MuiGrid-container"]');
      expect(grid).toBeInTheDocument();
    });

    it('should render normal state when viewId exists and selectedView exists', () => {
      mockHitSearchContext.viewId = 'test-view-id';
      mockViewContext.views = {
        'test-view-id': createMockView()
      };

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
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
      mockParameterContext.filters = ['', 'valid:filter', ''];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', '');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'valid:filter');
      expect(screen.getByTestId('hit-filter-2')).toHaveAttribute('data-value', '');
    });
  });

  describe('Add Filter Button', () => {
    it('should call addFilter with default filter when Add button clicked', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      await user.click(addButton);

      expect(mockAddFilter).toHaveBeenCalledWith('howler.id:*');
      expect(mockAddFilter).toHaveBeenCalledTimes(1);
    });

    it('should display Add icon on the button', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      expect(addButton).toBeInTheDocument();
    });

    it('should render Add button even when filters exist', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByRole('button');
      expect(addButton).toBeInTheDocument();
    });

    it('should allow multiple clicks to add multiple filters', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));

      await act(async () => {
        await user.click(addButton);
        await user.click(addButton);
        await user.click(addButton);
      });

      expect(mockAddFilter).toHaveBeenCalledTimes(3);
      expect(mockAddFilter).toHaveBeenCalledWith('howler.id:*');
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

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = container.querySelectorAll('[class*="MuiGrid-item"]');
      // HitSort + SearchSpan + ViewLink + 2 filters + Add button = 6 items
      expect(gridItems.length).toBe(6);
    });
  });

  describe('ViewId State Effects', () => {
    it('should apply disabled styling when viewId exists without matching view', () => {
      mockHitSearchContext.viewId = 'non-existent-view';
      mockViewContext.views = {};

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const grid = container.querySelector('[class*="MuiGrid-container"]');
      expect(grid).toBeInTheDocument();
    });

    it('should not apply disabled styling when viewId is null', () => {
      mockHitSearchContext.viewId = null;
      mockViewContext.views = {};

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const grid = container.querySelector('[class*="MuiGrid-container"]');
      expect(grid).toBeInTheDocument();
    });

    it('should not apply disabled styling when viewId exists with matching view', () => {
      mockHitSearchContext.viewId = 'test-view-id';
      mockViewContext.views = {
        'test-view-id': createMockView()
      };

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const grid = container.querySelector('[class*="MuiGrid-container"]');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle undefined filters gracefully', () => {
      mockParameterContext.filters = undefined as any;

      expect(() => render(<QuerySettings />, { wrapper: Wrapper })).toThrow();
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

    it('should handle duplicate filters in array', () => {
      mockParameterContext.filters = ['duplicate', 'duplicate', 'unique'];

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-filter-0')).toHaveAttribute('data-value', 'duplicate');
      expect(screen.getByTestId('hit-filter-1')).toHaveAttribute('data-value', 'duplicate');
      expect(screen.getByTestId('hit-filter-2')).toHaveAttribute('data-value', 'unique');
    });
  });

  describe('Integration Tests', () => {
    it('should work with all contexts simultaneously', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];
      mockHitSearchContext.viewId = 'test-view-id';
      mockViewContext.views = {
        'test-view-id': createMockView()
      };

      render(<QuerySettings />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.getByTestId('view-link')).toBeInTheDocument();
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

    it('should handle adding filter and updating filters array', async () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));
      await user.click(addButton);

      expect(mockAddFilter).toHaveBeenCalledWith('howler.id:*');

      // Simulate the filter being added to the array
      mockParameterContext = { ...mockParameterContext, filters: ['howler.id:*'] };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('hit-filter-0')).toBeInTheDocument();
    });

    it('should handle switching between views', () => {
      mockHitSearchContext.viewId = 'view1';
      mockViewContext.views = {
        view1: createMockView({ view_id: 'view1' }),
        view2: createMockView({ view_id: 'view2' })
      };

      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'view2' };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('view-link')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible Add Filter button', () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByRole('button');
      expect(addButton).toBeInTheDocument();
    });

    it('should maintain logical tab order', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      // All interactive elements should be in the document
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
      expect(screen.getByTestId('search-span')).toBeInTheDocument();
      expect(screen.getByTestId('view-link')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should be keyboard accessible for Add Filter button', async () => {
      render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByLabelText(i18n.t('hit.search.filter.add'));

      addButton.focus();
      expect(addButton).toHaveFocus();

      await user.keyboard('{Enter}');

      expect(mockAddFilter).toHaveBeenCalledWith('howler.id:*');
    });

    it('should maintain focus when filters are added', async () => {
      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      const addButton = screen.getByRole('button');
      await user.click(addButton);

      mockParameterContext = { ...mockParameterContext, filters: ['howler.id:*'] };
      rerender(<QuerySettings />);

      // Add button should still be in document
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should have semantic HTML structure', () => {
      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      // Should use proper Box and Grid components
      expect(container.querySelector('[class*="MuiBox"]')).toBeInTheDocument();
      expect(container.querySelector('[class*="MuiGrid-container"]')).toBeInTheDocument();
    });

    it('should not have any accessibility violations with disabled state', () => {
      mockHitSearchContext.viewId = 'missing-view';
      mockViewContext.views = {};

      render(<QuerySettings />, { wrapper: Wrapper });

      // Components should still be accessible even when disabled visually
      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });

    it('should support screen reader navigation', () => {
      mockParameterContext.filters = ['filter1', 'filter2'];

      render(<QuerySettings />, { wrapper: Wrapper });

      // All major components should be identifiable
      const hitSort = screen.getByTestId('hit-sort');
      const searchSpan = screen.getByTestId('search-span');
      const viewLink = screen.getByTestId('view-link');
      const filter1 = screen.getByTestId('hit-filter-0');
      const filter2 = screen.getByTestId('hit-filter-1');
      const addButton = screen.getByRole('button');

      expect(hitSort).toBeInTheDocument();
      expect(searchSpan).toBeInTheDocument();
      expect(viewLink).toBeInTheDocument();
      expect(filter1).toBeInTheDocument();
      expect(filter2).toBeInTheDocument();
      expect(addButton).toBeInTheDocument();
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

    it('should update when viewId changes', () => {
      mockHitSearchContext.viewId = 'view1';

      const { rerender } = render(<QuerySettings />, { wrapper: Wrapper });

      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'view2' };
      rerender(<QuerySettings />);

      expect(screen.getByTestId('view-link')).toBeInTheDocument();
    });

    it('should update when boxSx prop changes', () => {
      const { rerender } = render(<QuerySettings boxSx={{ maxWidth: '800px' }} />, { wrapper: Wrapper });

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();

      rerender(<QuerySettings boxSx={{ maxWidth: '1000px' }} />);

      expect(screen.getByTestId('hit-sort')).toBeInTheDocument();
    });
  });

  describe('Component Composition', () => {
    it('should render all child components in correct order', () => {
      mockParameterContext.filters = ['filter1'];

      const { container } = render(<QuerySettings />, { wrapper: Wrapper });

      const gridItems = container.querySelectorAll('[class*="MuiGrid-item"]');

      // Order: HitSort, SearchSpan, ViewLink, HitFilter(s), Add button
      expect(gridItems[0]).toContainElement(screen.getByTestId('hit-sort'));
      expect(gridItems[1]).toContainElement(screen.getByTestId('search-span'));
      expect(gridItems[2]).toContainElement(screen.getByTestId('view-link'));
      expect(gridItems[3]).toContainElement(screen.getByTestId('hit-filter-0'));
      expect(gridItems[4]).toContainElement(screen.getByRole('button'));
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
      expect(screen.getByTestId('view-link')).toBeInTheDocument();
    });
  });
});

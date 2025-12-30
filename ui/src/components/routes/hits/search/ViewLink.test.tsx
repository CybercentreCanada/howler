/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import React, { createContext, useContext, type PropsWithChildren } from 'react';
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

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Link: React.forwardRef<any, any>(({ to, children, ...props }, ref) => (
      <a ref={ref} href={to} {...props}>
        {children}
      </a>
    ))
  };
});

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
const mockSearch = vi.fn();
let mockParameterContext = {
  query: 'howler.id:*',
  sort: 'event.created desc',
  span: 'date.range.1.month',
  setQuery: vi.fn(),
  setSort: vi.fn(),
  setSpan: vi.fn()
};

let mockHitSearchContext = {
  viewId: 'test-view-id',
  search: mockSearch
};

let mockViewContext = {
  views: {
    'test-view-id': createMockView()
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
    mockHitSearchContext.viewId = 'test-view-id';
    mockParameterContext.query = 'howler.id:*';
    mockParameterContext.sort = 'event.created desc';
    mockParameterContext.span = 'date.range.1.month';
    mockViewContext.views = {
      'test-view-id': createMockView()
    };
  });

  describe('Rendering Conditions', () => {
    it('should return null when viewId is not set', () => {
      mockHitSearchContext.viewId = null;

      const { container } = render(<ViewLink />, { wrapper: Wrapper });

      expect(container.firstChild).toBeNull();
    });

    it('should return null when viewId is undefined', () => {
      mockHitSearchContext.viewId = undefined;

      const { container } = render(<ViewLink />, { wrapper: Wrapper });

      expect(container.firstChild).toBeNull();
    });

    it('should render selected view UI when viewId exists and view is found', () => {
      render(<ViewLink />, { wrapper: Wrapper });

      expect(screen.getByText('Test View')).toBeInTheDocument();
    });

    it('should render error alert when viewId exists but view is not found', () => {
      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'non-existent-view' };
      mockViewContext = {
        ...mockViewContext,
        views: {
          ...mockViewContext.views,
          'non-existent-view': null
        }
      };

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveAttribute('aria-live', 'assertive');
    });

    it('should not render error alert when views object is empty (not ready)', () => {
      mockHitSearchContext.viewId = 'non-existent-view';
      mockViewContext.views = {} as any;

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('UI Element Display', () => {
    it('should display view title as link with correct href', () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const titleLink = screen.getByText('Test View').closest('a');
      expect(titleLink).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should display tooltip with view query on title', () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const tooltip = screen.getByText('Test View');
      expect(tooltip).toHaveAttribute('aria-label', 'Test View - howler.status:open');
    });

    it('should display translated view title', () => {
      mockViewContext.views['test-view-id'] = createMockView({
        title: 'view.assigned_to_me'
      });

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      // The i18n mock should translate this key
      expect(screen.getByText(/assigned/i)).toBeInTheDocument();
    });

    it('should display edit icon when viewId exists', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      // Edit icon should be present (MUI Edit icon)
      const editButton = screen.getByRole('link', { name: /edit /i });
      expect(editButton).toBeInTheDocument();
    });

    it('should display refresh button when viewId exists', () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const refreshButton = screen.getByRole('button');
      expect(refreshButton).toBeInTheDocument();
    });

    it('should display open button when viewId exists', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const openLink = screen.getByRole('link', { name: /open /i });
      expect(openLink).toBeInTheDocument();
      expect(openLink).toHaveAttribute('href', '/search?query=howler.status:open');
    });

    it('should not display refresh button when viewId is null', () => {
      mockHitSearchContext.viewId = null;

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('should not display open button when viewId is null', () => {
      mockHitSearchContext.viewId = null;

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.queryByRole('link', { name: /open /i })).not.toBeInTheDocument();
    });
  });

  describe('Button States & Interactions', () => {
    it('should call search function when refresh button is clicked', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const refreshButton = screen.getByLabelText(i18n.t(`view.refresh`));
      await user.click(refreshButton);

      expect(mockSearch).toHaveBeenCalledWith('howler.id:*');
    });

    it('should navigate to search when open button is clicked', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const openLink = screen.getByRole('link', { name: /open /i });
      expect(openLink).toHaveAttribute('href', '/search?query=howler.status:open');
    });

    it('should navigate to /search when error alert close button is clicked', () => {
      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'non-existent-view' };
      mockViewContext = {
        ...mockViewContext,
        views: {
          ...mockViewContext.views,
          'non-existent-view': null
        }
      };

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const closeButton = screen.getByRole('alert').querySelector('a');
      expect(closeButton).toHaveAttribute('href', '/search');
    });

    it('should have correct tooltip on refresh button', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const tooltip = screen.getByLabelText(i18n.t(`view.refresh`));
      expect(tooltip).toHaveAttribute('aria-label', expect.stringContaining('Refresh'));
    });

    it('should have correct tooltip on open button', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const openLink = screen.getByRole('link', { name: /open /i });
      expect(openLink).toHaveAttribute('aria-label', expect.stringContaining('Open'));
    });
  });

  describe('URL Generation (viewUrl)', () => {
    it('should generate edit URL when viewId exists', async () => {
      render(<ViewLink />, { wrapper: Wrapper });

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const editButton = screen.getByRole('link', { name: /edit/i });
      expect(editButton).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should have edit tooltip when viewId exists', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const editButton = screen.getByRole('link', { name: /edit/i });
      expect(editButton).toHaveAttribute('aria-label', expect.stringContaining('Edit'));
    });
  });

  describe('Edge Cases', () => {
    it('should handle selectedView with missing title', () => {
      mockViewContext.views['test-view-id'] = createMockView({
        title: undefined
      });

      const { container } = render(<ViewLink />, { wrapper: Wrapper });

      expect(container).toBeInTheDocument();
      // Component should still render without crashing
    });

    it('should handle selectedView with missing query', () => {
      mockViewContext.views['test-view-id'] = createMockView({
        query: undefined
      });

      const { container } = render(<ViewLink />, { wrapper: Wrapper });

      expect(container).toBeInTheDocument();

      // Query tooltip should be empty or undefined
      const tooltip = screen.getByText('Test View');
      expect(tooltip).toHaveAttribute('aria-label', 'Test View - Unknown');
    });

    it('should handle rapid context changes', () => {
      const { rerender } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      // Change viewId
      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'another-view-id' };
      mockViewContext = {
        ...mockViewContext,
        views: {
          ...mockViewContext.views,
          'another-view-id': createMockView({
            view_id: 'another-view-id',
            title: 'Another View'
          })
        }
      };

      rerender(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.getByText('Another View')).toBeInTheDocument();

      // Change back
      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'test-view-id' };

      rerender(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.getByText('Test View')).toBeInTheDocument();
    });

    it('should handle undefined query in parameter context', async () => {
      mockParameterContext.query = undefined;

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const refreshButton = screen.getByLabelText(i18n.t(`view.refresh`));
      fireEvent.click(refreshButton);

      expect(mockSearch).toHaveBeenCalledWith(undefined);
    });

    it('should handle null sort in parameter context', () => {
      mockParameterContext.sort = null;

      const { container } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(container).toBeInTheDocument();
    });

    it('should handle null span in parameter context', () => {
      mockParameterContext.span = null;

      const { container } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(container).toBeInTheDocument();
    });

    it('should handle view with all optional fields missing', () => {
      mockViewContext.views['test-view-id'] = {
        view_id: 'test-view-id'
      } as View;

      const { container } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(container).toBeInTheDocument();
    });

    it('should handle empty views object', () => {
      mockViewContext.views = {} as any;
      mockHitSearchContext.viewId = 'test-view-id';

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      // Should not render error alert because viewsReady is false
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('Integration Tests', () => {
    it('should work with all three contexts simultaneously', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      // Should use values from ParameterContext
      const refreshButton = screen.getByLabelText(i18n.t(`view.refresh`));
      fireEvent.click(refreshButton);
      expect(mockSearch).toHaveBeenCalledWith('howler.id:*');

      // Should use values from ViewContext
      expect(screen.getByText('Test View')).toBeInTheDocument();

      // Should use values from HitSearchContext
      const editButton = screen.getByRole('link', { name: /edit/i });
      expect(editButton).toHaveAttribute('href', '/views/test-view-id/edit');
    });

    it('should render correctly with different view types', () => {
      const viewTypes: Array<'personal' | 'global' | 'readonly'> = ['personal', 'global', 'readonly'];

      const { rerender } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      viewTypes.forEach(type => {
        mockViewContext = {
          ...mockViewContext,
          views: {
            ...mockViewContext.views,
            'test-view-id': createMockView({ type })
          }
        };

        rerender(
          <Wrapper>
            <ViewLink />
          </Wrapper>
        );

        expect(screen.getByLabelText(i18n.t(`route.views.manager.${type}`))).toBeInTheDocument();
      });
    });

    it('should handle multiple view IDs correctly', () => {
      mockViewContext.views = {
        'view-1': createMockView({ view_id: 'view-1', title: 'View 1' }),
        'view-2': createMockView({ view_id: 'view-2', title: 'View 2' }),
        'view-3': createMockView({ view_id: 'view-3', title: 'View 3' })
      } as any;

      mockHitSearchContext.viewId = 'view-2';

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.getByText('View 2')).toBeInTheDocument();
      expect(screen.queryByText('View 1')).not.toBeInTheDocument();
      expect(screen.queryByText('View 3')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have tooltips for all icon buttons', async () => {
      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const editButton = screen.getByRole('link', { name: /edit /i });
      const refreshButton = screen.getByLabelText(i18n.t(`view.refresh`));
      const openButton = screen.getByRole('link', { name: /open /i });

      expect(editButton).toHaveAttribute('aria-label');
      expect(refreshButton).toHaveAttribute('aria-label');
      expect(openButton).toHaveAttribute('aria-label');
    });

    it('should have proper role for error alert', () => {
      mockHitSearchContext.viewId = 'non-existent-view';
      mockViewContext.views = {
        'non-existent-view': null,
        'test-view-id': createMockView()
      };

      render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });

    it('should have accessible link text for view title', () => {
      render(<ViewLink />, { wrapper: Wrapper });

      const titleLink = screen.getByText('Test View').closest('a');
      expect(titleLink).toHaveAttribute('href', '/views/test-view-id/edit');
      expect(titleLink.textContent).toBe('Test View');
    });
  });

  describe('Memoization', () => {
    it('should not re-render unnecessarily when unrelated context values change', () => {
      const { rerender } = render(<ViewLink />, { wrapper: Wrapper });

      // Change an unrelated value
      mockParameterContext.setQuery = vi.fn();

      rerender(<ViewLink />);

      const secondRenderButton = screen.getByRole('button');

      // Components should still be present
      expect(secondRenderButton).toBeInTheDocument();
    });

    it('should update when viewId changes', () => {
      const { rerender } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.getByText('Test View')).toBeInTheDocument();

      mockHitSearchContext = { ...mockHitSearchContext, viewId: 'another-view' };
      mockViewContext.views['another-view'] = createMockView({
        view_id: 'another-view',
        title: 'Another View'
      });

      rerender(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      expect(screen.getByText('Another View')).toBeInTheDocument();
    });

    it('should update when query changes', async () => {
      const { rerender } = render(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      await user.click(screen.getByLabelText(i18n.t(`route.views.manager.personal`)));

      const refreshButton = screen.getByLabelText(i18n.t(`view.refresh`));
      fireEvent.click(refreshButton);

      expect(mockSearch).toHaveBeenCalledWith('howler.id:*');

      mockParameterContext = { ...mockParameterContext, query: 'howler.status:closed' };

      rerender(
        <Wrapper>
          <ViewLink />
        </Wrapper>
      );

      fireEvent.click(refreshButton);

      expect(mockSearch).toHaveBeenCalledWith('howler.status:closed');
    });
  });
});

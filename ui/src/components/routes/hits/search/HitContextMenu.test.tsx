/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { omit } from 'lodash-es';
import { act, createContext, useContext, type PropsWithChildren } from 'react';
import { vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Mock API
vi.mock('api', { spy: true });

vi.mock('use-context-selector', async () => {
  return {
    createContext,
    useContextSelector: (context, selector) => {
      return selector(useContext(context));
    }
  };
});

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    Link: ({ to, children, ...props }) => (
      <a href={to} {...props}>
        {children}
      </a>
    )
  };
});

// Mock custom hooks
const mockAssess = vi.hoisted(() => vi.fn());
const mockVote = vi.hoisted(() => vi.fn());
const mockTransitionFunction = vi.hoisted(() => vi.fn());
const mockAvailableTransitions = vi.hoisted(() => [
  {
    type: 'action',
    name: 'escalate',
    actionFunction: mockTransitionFunction,
    i18nKey: 'hit.actions.escalate'
  }
]);

vi.mock('components/hooks/useHitActions', () => ({
  default: vi.fn(() => ({
    availableTransitions: mockAvailableTransitions,
    canVote: true,
    canAssess: true,
    assess: mockAssess,
    vote: mockVote
  }))
}));

const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn());
const mockGetMatchingTemplate = vi.hoisted(() => vi.fn());
vi.mock('components/app/hooks/useMatchers', () => ({
  default: vi.fn(() => ({
    getMatchingAnalytic: mockGetMatchingAnalytic,
    getMatchingTemplate: mockGetMatchingTemplate
  }))
}));

const mockDispatchApi = vi.fn();
vi.mock('components/hooks/useMyApi', () => ({
  default: vi.fn(() => ({
    dispatchApi: mockDispatchApi
  }))
}));

const mockExecuteAction = vi.hoisted(() => vi.fn());
vi.mock('components/routes/action/useMyActionFunctions', () => ({
  default: vi.fn(() => ({
    executeAction: mockExecuteAction
  }))
}));

// Mock context providers

// Mock plugin store
const mockPluginStoreExecuteFunction = vi.hoisted(() => vi.fn(() => []));
vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({
    executeFunction: mockPluginStoreExecuteFunction
  })
}));

vi.mock('plugins/store', () => ({
  default: {
    plugins: ['plugin1']
  }
}));

// Mock MUI components
vi.mock('@mui/material', async () => {
  const actual: any = await vi.importActual('@mui/material');
  return {
    ...actual,
    Menu: ({ children, open, onClose, ...props }) =>
      open ? (
        <div
          role="menu"
          onClick={onClose}
          {...omit(props, ['sx', 'slotProps', 'MenuListProps', 'anchorOrigin', 'anchorEl'])}
        >
          {children}
        </div>
      ) : null,
    MenuItem: ({ children, onClick, disabled, component, to, ...props }) => {
      const Component = component || 'div';
      return (
        <Component
          role="menuitem"
          onClick={onClick}
          aria-disabled={disabled}
          href={to}
          {...omit(props, ['sx', 'component'])}
        >
          {children}
        </Component>
      );
    },
    Fade: ({ children, in: inProp }) => (inProp ? <>{children}</> : null),
    ListItemIcon: ({ children }) => <div>{children}</div>,
    ListItemText: ({ children }) => <div>{children}</div>,
    Divider: () => <hr />,
    Box: ({ children, ...props }) => <div {...omit(props, ['sx'])}>{children}</div>
  };
});

// Import component after mocks
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import i18n from 'i18n';
import type { Hit } from 'models/entities/generated/Hit';
import { I18nextProvider } from 'react-i18next';
import { createMockAction, createMockAnalytic, createMockHit, createMockTemplate } from 'tests/utils';
import { DEFAULT_QUERY } from 'utils/constants';
import HitContextMenu from './HitContextMenu';

const mockGetSelectedId = vi.fn(() => 'test-hit-1');
const mockConfig = {
  lookups: {
    'howler.assessment': ['legitimate', 'false_positive', 'unrelated']
  }
};

const mockApiContext = { config: mockConfig };
const mockHitContext = {
  hits: {
    'test-hit-1': createMockHit()
  },
  selectedHits: [] as Hit[]
};
const mockParameterContext = { query: DEFAULT_QUERY, setQuery: vi.fn() };

// Test wrapper
const Wrapper = ({ children }: PropsWithChildren) => {
  return (
    <I18nextProvider i18n={i18n as any}>
      <ApiConfigContext.Provider value={mockApiContext as any}>
        <HitContext.Provider value={mockHitContext as any}>
          <ParameterContext.Provider value={mockParameterContext as any}>{children}</ParameterContext.Provider>
        </HitContext.Provider>
      </ApiConfigContext.Provider>
    </I18nextProvider>
  );
};

describe('HitContextMenu', () => {
  let user: UserEvent;
  let rerender: ReturnType<typeof render>['rerender'];

  beforeEach(() => {
    user = userEvent.setup();

    vi.clearAllMocks();
    mockHitContext.selectedHits.length = 0;

    mockHitContext.hits['test-hit-1'] = createMockHit();

    mockGetMatchingAnalytic.mockResolvedValue(createMockAnalytic());
    mockGetMatchingTemplate.mockResolvedValue(createMockTemplate());

    rerender = render(
      <Wrapper>
        <HitContextMenu getSelectedId={mockGetSelectedId}>
          <div>Test Content</div>
        </HitContextMenu>
      </Wrapper>
    ).rerender;
  });

  describe('Context Menu Initialization', () => {
    it('should open menu on right-click', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
    });

    it('should call getSelectedId with mouse event on right-click', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(mockGetSelectedId).toHaveBeenCalled();
        expect((mockGetSelectedId.mock.calls as string[][])[0][0]).toBeInstanceOf(Object);
      });
    });

    it('should close menu when clicking on it', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const menu = screen.getByRole('menu');
        user.click(menu);
      });

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('should close and reopen when right-clicking while menu is open', async () => {
      const contextMenuWrapper = screen.getByText('Test Content').parentElement;

      act(() => {
        // Open menu
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        // Right-click again
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('should render base menu items', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getAllByText(/open/i)).toHaveLength(2);
      });
    });

    it('should disable "Open Hit" when hit is null', async () => {
      act(() => {
        mockHitContext.hits['test-hit-1'] = null;

        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        const menuItems = screen.getAllByRole('menuitem');
        const openHitItem = menuItems.find(item => item.textContent?.toLowerCase().includes('open hit viewer'));

        expect(openHitItem).toHaveAttribute('aria-disabled', 'true');
      });
    });

    it('should fetch actions from API on menu open', async () => {
      const mockActions = [createMockAction()];
      mockDispatchApi.mockResolvedValue({ items: mockActions });

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(mockDispatchApi).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ throwError: false }));
      });
    });
  });

  describe('Action Type Submenus', () => {
    it('should show assessment submenu on hover when canAssess is true', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const assessmentMenuItem = screen.getByText('Assess');
      expect(assessmentMenuItem).toBeInTheDocument();

      act(() => {
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('assessment-submenu')).toBeInTheDocument();
      });
    });

    it('should filter assessments by analytic valid_assessments', async () => {
      mockGetMatchingAnalytic.mockResolvedValue(
        createMockAnalytic({
          triage_settings: {
            valid_assessments: ['legitimate'],
            skip_rationale: false
          }
        })
      );

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      act(() => {
        const assessmentMenuItem = screen.getByText('Assess');
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        const submenu = screen.getByTestId('assessment-submenu');
        expect(submenu).toBeInTheDocument();
        expect(submenu.textContent).toContain('Legitimate');
        expect(submenu.textContent).not.toContain('False_positive');
      });
    });

    it('should show vote submenu when canVote is true', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const voteMenuItem = screen.getByText('Vote');
      expect(voteMenuItem).toBeInTheDocument();

      act(() => {
        fireEvent.mouseEnter(voteMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('vote-submenu')).toBeInTheDocument();
      });
    });

    it('should show transition submenu with available transitions', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const actionMenuItem = screen.getByText('Run Action');
      expect(actionMenuItem).toBeInTheDocument();

      act(() => {
        fireEvent.mouseEnter(actionMenuItem);
      });

      await waitFor(() => {
        const submenu = screen.getByTestId('actions-submenu');
        expect(submenu).toBeInTheDocument();
        expect(submenu.textContent).toContain('Test Action');
      });
    });

    it('should show custom actions submenu with fetched actions', async () => {
      const mockActions = [
        createMockAction({ action_id: 'action-1', name: 'Custom Action 1' }),
        createMockAction({ action_id: 'action-2', name: 'Custom Action 2' })
      ];
      mockDispatchApi.mockResolvedValue({ items: mockActions });

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(mockDispatchApi).toHaveBeenCalled();
      });

      const actionsMenuItem = screen.getByText('Run Action');
      expect(actionsMenuItem).toBeInTheDocument();

      act(() => {
        fireEvent.mouseEnter(actionsMenuItem);
      });

      await waitFor(() => {
        const submenu = screen.getByTestId('actions-submenu');
        expect(submenu).toBeInTheDocument();
        expect(submenu.textContent).toContain('Custom Action 1');
        expect(submenu.textContent).toContain('Custom Action 2');
      });
    });

    it('should hide submenu on mouse leave', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const assessmentMenuItem = screen.getByText('Assess');
      act(() => {
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('assessment-submenu')).toBeInTheDocument();
      });

      act(() => {
        fireEvent.mouseLeave(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.queryByTestId('assessment-submenu')).toBeNull();
      });
    });

    it('should disable custom actions menu when no actions are available', async () => {
      mockDispatchApi.mockResolvedValueOnce({ items: [] });

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        const actionsMenuItem = screen.getByTestId('actions-menu-item');
        expect(actionsMenuItem).toHaveAttribute('aria-disabled', 'true');
      });
    });
  });

  describe('Action Execution', () => {
    it('should call assess with selected assessment', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const assessmentMenuItem = screen.getByText('Assess');
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('assessment-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const legitimateOption = screen.getByText('Legitimate');
        await user.click(legitimateOption);
      });

      await waitFor(() => {
        expect(mockAssess).toHaveBeenCalledWith('legitimate', false);
      });
    });

    it('should call assess with skip_rationale from analytic settings', async () => {
      mockGetMatchingAnalytic.mockResolvedValue(
        createMockAnalytic({
          triage_settings: {
            valid_assessments: ['legitimate'],
            skip_rationale: true
          }
        })
      );

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const assessmentMenuItem = screen.getByText('Assess');
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('assessment-submenu')).toBeInTheDocument();
      });

      const legitimateOption = screen.getByText('Legitimate');
      await user.click(legitimateOption);

      await waitFor(() => {
        expect(mockAssess).toHaveBeenCalledWith('legitimate', true);
      });
    });

    it('should call vote with lowercased vote option', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const voteMenuItem = screen.getByText('Vote');
        fireEvent.mouseEnter(voteMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('vote-submenu')).toBeInTheDocument();
      });

      const upvoteOption = screen.getByText('Benign');
      await user.click(upvoteOption);

      await waitFor(() => {
        expect(mockVote).toHaveBeenCalledWith('benign');
      });
    });

    it('should call transition actionFunction on click', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const actionsMenuItem = screen.getByText('Run Action');
        fireEvent.mouseEnter(actionsMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('actions-submenu').childNodes[0]).not.toBeEmptyDOMElement();
      });

      await act(async () => {
        const escalateOption = screen.getByText('Custom Action 1');
        await user.click(escalateOption);
      });

      await waitFor(() => {
        expect(mockExecuteAction).toHaveBeenCalled();
      });
    });

    it('should call executeAction with action_id and hit query', async () => {
      const mockActions = [createMockAction({ action_id: 'action-1', name: 'Custom Action' })];
      mockDispatchApi.mockResolvedValue({ items: mockActions });

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      let actionsMenuItem: HTMLElement;
      await waitFor(() => {
        actionsMenuItem = screen.getByText('Run Action');
        expect(actionsMenuItem).toBeInTheDocument();
      });

      act(() => {
        fireEvent.mouseEnter(actionsMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('actions-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const customActionOption = screen.getByText('Custom Action');
        await user.click(customActionOption);
      });

      await waitFor(() => {
        expect(mockExecuteAction).toHaveBeenCalledWith('action-1', 'howler.id:test-hit-1');
      });
    });

    it('should close menu after action execution', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const voteMenuItem = screen.getByText('Vote');
        fireEvent.mouseEnter(voteMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('vote-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const benignOption = screen.getByText('Benign');
        await user.click(benignOption);
      });

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });
  });

  describe('Exclusion Filter Functionality', () => {
    beforeEach(() => {
      mockGetMatchingTemplate.mockResolvedValue(
        createMockTemplate({
          keys: ['howler.detection', 'event.id']
        })
      );

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );
    });

    it('should render exclusion submenu with template keys', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const excludesMenuItem = screen.getByText('Exclude By');
        fireEvent.mouseEnter(excludesMenuItem);
      });

      await waitFor(() => {
        const submenu = screen.getByTestId('excludes-submenu');
        expect(submenu).toBeInTheDocument();
        expect(submenu.textContent).toContain('howler.detection');
        expect(submenu.textContent).toContain('event.id');
      });
    });

    it('should generate exclusion query for single value', async () => {
      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        const excludesMenuItem = screen.getByText('Exclude By');
        fireEvent.mouseEnter(excludesMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('excludes-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const detectionKey = screen.getByText('howler.detection');
        await user.click(detectionKey);
      });

      await waitFor(() => {
        expect(mockParameterContext.setQuery).toHaveBeenCalledWith('-howler.detection:"Test Detection"');
      });
    });

    it('should generate exclusion query for array values', async () => {
      mockGetMatchingTemplate.mockResolvedValue(
        createMockTemplate({
          keys: ['howler.outline.indicators']
        })
      );

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        const excludesMenuItem = screen.getByText('Exclude By');
        fireEvent.mouseEnter(excludesMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('excludes-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const tagsKey = screen.getByText('howler.outline.indicators');
        await user.click(tagsKey);
      });

      await waitFor(() => {
        expect(mockParameterContext.setQuery).toHaveBeenCalledWith('-howler.outline.indicators:("a" OR "b" OR "c")');
      });
    });

    it('should preserve existing query when adding exclusion', async () => {
      mockParameterContext.query = 'howler.status:open';

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        const excludesMenuItem = screen.getByText('Exclude By');
        fireEvent.mouseEnter(excludesMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('excludes-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        const detectionKey = screen.getByText('howler.detection');
        await user.click(detectionKey);
      });

      await waitFor(() => {
        expect(mockParameterContext.setQuery).toHaveBeenCalledWith(
          '(howler.status:open) AND -howler.detection:"Test Detection"'
        );
      });
    });

    it('should not render exclusion menu when template has no keys', async () => {
      mockGetMatchingTemplate.mockResolvedValue(
        createMockTemplate({
          keys: []
        })
      );

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      expect(screen.queryByText('Exclude By')).toBeNull();
    });

    it('should skip null field values in exclusion menu', async () => {
      act(() => {
        mockHitContext.hits['test-hit-1'].event = {};
      });

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        const excludesMenuItem = screen.getByText('Exclude By');
        fireEvent.mouseEnter(excludesMenuItem);
      });

      await waitFor(() => {
        const submenu = screen.getByTestId('excludes-submenu');
        expect(submenu).toBeInTheDocument();
        expect(submenu.textContent).toContain('howler.detection');
        expect(submenu.textContent).not.toContain('event.id');
      });
    });
  });

  describe('Multiple Hit Selection', () => {
    it('should use selectedHits when current hit is included', async () => {
      act(() => {
        mockHitContext.hits['hit-1'] = createMockHit({ howler: { id: 'hit-1' } });
        mockHitContext.hits['hit-2'] = createMockHit({ howler: { id: 'hit-2' } });
        mockHitContext.selectedHits.push(mockHitContext.hits['hit-1'], mockHitContext.hits['hit-2']);
        mockGetSelectedId.mockReturnValue('hit-1');
      });

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      // The component should use selectedHits for actions
      // We can verify this indirectly through the useHitActions hook receiving the right data
      expect(mockGetSelectedId).toHaveBeenCalled();
    });

    it('should use only current hit when not in selectedHits', async () => {
      act(() => {
        mockHitContext.hits['hit-1'] = createMockHit({ howler: { id: 'hit-1' } });
        mockHitContext.selectedHits.push(mockHitContext.hits['hit-1']);
        mockGetSelectedId.mockReturnValue('test-hit-1');
      });

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      expect(mockGetSelectedId).toHaveBeenCalled();
    });
  });

  describe('Dynamic Data Loading', () => {
    let contextMenuWrapper: HTMLElement;
    beforeEach(() => {
      contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);
    });

    it('should call getMatchingAnalytic when hit has analytic', async () => {
      await waitFor(() => {
        expect(mockGetMatchingAnalytic).toHaveBeenCalledWith(mockHitContext.hits['test-hit-1']);
      });
    });

    it('should call getMatchingTemplate when menu opens', async () => {
      await waitFor(() => {
        expect(mockGetMatchingTemplate).toHaveBeenCalledWith(mockHitContext.hits['test-hit-1']);
      });
    });

    it('should reset state when menu closes', async () => {
      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      act(() => {
        // Hover to show submenu
        const assessmentMenuItem = screen.getByText('Assess');
        fireEvent.mouseEnter(assessmentMenuItem);
      });

      await waitFor(() => {
        expect(screen.getByTestId('assessment-submenu')).toBeInTheDocument();
      });

      await act(async () => {
        // Close menu
        const menu = screen.getByRole('menu');
        await user.click(menu);
      });

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });

      act(() => {
        // Reopen to verify state was reset
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
        // Submenu should not be visible without hover
        expect(screen.queryByTestId('assessment-submenu')).toBeNull();
      });
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should not crash when hit is null', async () => {
      act(() => {
        mockHitContext.hits = {} as any;
      });

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      expect(screen.queryByRole('menu')).toBeInTheDocument();
    });

    it('should not render exclusion menu when template is null', async () => {
      mockGetMatchingTemplate.mockResolvedValue(null);

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      act(() => {
        const contextMenuWrapper = screen.getByText('Test Content').parentElement;
        fireEvent.contextMenu(contextMenuWrapper);
      });

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.queryByText('Exclude By')).toBeNull();
      });
    });

    it('should handle API failure gracefully', async () => {
      mockDispatchApi.mockResolvedValue(null);

      rerender(
        <Wrapper>
          <HitContextMenu getSelectedId={mockGetSelectedId}>
            <div>Test Content</div>
          </HitContextMenu>
        </Wrapper>
      );

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const actionsMenuItem = screen.getByTestId('actions-menu-item');
      expect(actionsMenuItem).toHaveAttribute('aria-disabled', 'true');
    });

    it('should not call getMatchingAnalytic or getMatchingTemplate when hit has no analytic', async () => {
      act(() => {
        mockHitContext.hits['test-hit-1'].howler.analytic = null;
      });

      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      expect(mockGetMatchingAnalytic).not.toHaveBeenCalled();
    });

    it('should call plugin store with hits array', async () => {
      const contextMenuWrapper = screen.getByText('Test Content').parentElement;
      fireEvent.contextMenu(contextMenuWrapper);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      // Plugin store should be called during menu render
      expect(mockPluginStoreExecuteFunction).toHaveBeenCalled();
    });
  });
});

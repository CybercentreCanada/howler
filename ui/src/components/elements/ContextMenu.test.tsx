import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { omit } from 'lodash-es';
import { act } from 'react';
import { vi } from 'vitest';

// Mock react-router-dom Link
vi.mock('react-router-dom', () => ({
  Link: ({ to, children, ...props }: any) => (
    <a href={to} {...props}>
      {children}
    </a>
  )
}));

// Stub MUI components to simple HTML equivalents
vi.mock('@mui/material', async () => {
  const actual: any = await vi.importActual('@mui/material');
  return {
    ...actual,
    useTheme: () => ({ shape: { borderRadius: 4 } }),
    Menu: ({ children, open, onClose, ...props }: any) =>
      open ? (
        <div
          role="menu"
          onClick={onClose}
          {...omit(props, ['sx', 'slotProps', 'MenuListProps', 'anchorOrigin', 'anchorEl'])}
        >
          {children}
        </div>
      ) : null,
    MenuItem: ({ children, onClick, disabled, component, to, id, onMouseEnter, onMouseLeave, ...props }: any) => {
      const Component = component || 'div';
      return (
        <Component
          role="menuitem"
          onClick={onClick}
          aria-disabled={disabled}
          href={to}
          id={id}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          {...omit(props, ['sx'])}
        >
          {children}
        </Component>
      );
    },
    Fade: ({ children, in: inProp }: any) => (inProp ? <>{children}</> : null),
    ListItemIcon: ({ children }: any) => <div>{children}</div>,
    ListItemText: ({ children }: any) => <div>{children}</div>,
    Divider: () => <hr />,
    Paper: ({ children, id, ...props }: any) => (
      <div id={id} {...omit(props, ['sx', 'elevation'])}>
        {children}
      </div>
    ),
    MenuList: ({ children, ...props }: any) => (
      <div role="group" {...omit(props, ['sx', 'dense'])}>
        {children}
      </div>
    ),
    Box: ({ children, id, onContextMenu, ...props }: any) => (
      <div id={id} onContextMenu={onContextMenu} {...omit(props, ['sx'])}>
        {children}
      </div>
    )
  };
});

import ContextMenu, { type ContextMenuEntry } from './ContextMenu';

const renderMenu = (
  items: ContextMenuEntry[],
  opts: { onOpen?: ReturnType<typeof vi.fn>; onClose?: ReturnType<typeof vi.fn>; autoOpen?: boolean } = {}
) => {
  const { autoOpen = true, onOpen = vi.fn(), onClose = vi.fn() } = opts;
  const utils = render(
    <ContextMenu items={items} onOpen={onOpen} onClose={onClose} id="test-menu">
      <div id="trigger">trigger</div>
    </ContextMenu>
  );
  const openMenu = () =>
    act(() => {
      fireEvent.contextMenu(screen.getByTestId('trigger'));
    });
  if (autoOpen) {
    openMenu();
  }
  return { ...utils, onOpen, onClose, openMenu };
};

describe('ContextMenu', () => {
  describe('Visibility', () => {
    it('renders nothing before right-click', () => {
      const { container } = renderMenu([], { autoOpen: false });
      expect(container.querySelector('[role="menu"]')).toBeNull();
    });

    it('renders the menu after right-click', () => {
      renderMenu([]);
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    it('calls onClose when the menu is clicked', () => {
      const { onClose } = renderMenu([]);
      fireEvent.click(screen.getByRole('menu'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('closes on a second right-click (toggle)', () => {
      const { openMenu } = renderMenu([]);
      expect(screen.getByRole('menu')).toBeInTheDocument();
      openMenu();
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });

    it('calls onOpen when right-clicked', () => {
      const onOpen = vi.fn();
      renderMenu([], { onOpen });
      expect(onOpen).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when closed via toggle right-click', () => {
      const onClose = vi.fn();
      const { openMenu } = renderMenu([], { onClose });
      openMenu();
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Leaf items', () => {
    it('renders a plain button item', () => {
      const onClick = vi.fn();
      renderMenu([{ kind: 'item', id: 'action-1', label: 'Do something', onClick }]);

      const item = screen.getByRole('menuitem');
      expect(item).toHaveTextContent('Do something');
    });

    it('calls onClick when a plain item is clicked', () => {
      const onClick = vi.fn();
      renderMenu([{ kind: 'item', id: 'action-1', label: 'Do something', onClick }]);

      fireEvent.click(screen.getByRole('menuitem'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('renders a link item with correct href', () => {
      renderMenu([{ kind: 'item', id: 'link-1', label: 'Go somewhere', to: '/some/path' }]);

      const link = screen.getByRole('menuitem');
      expect(link).toHaveAttribute('href', '/some/path');
    });

    it('marks a disabled item with aria-disabled', () => {
      renderMenu([{ kind: 'item', id: 'action-1', label: 'Disabled', disabled: true }]);

      expect(screen.getByRole('menuitem')).toHaveAttribute('aria-disabled', 'true');
    });

    it('renders an icon alongside the label when provided', () => {
      renderMenu([{ kind: 'item', id: 'icon-item', label: 'With icon', icon: <span id="test-icon" /> }]);

      expect(screen.getByTestId('test-icon')).toBeInTheDocument();
      expect(screen.getByRole('menuitem')).toHaveTextContent('With icon');
    });
  });

  describe('Dividers', () => {
    it('renders a divider between items', () => {
      renderMenu([
        { kind: 'item', id: 'item-a', label: 'A' },
        { kind: 'divider', id: 'sep' },
        { kind: 'item', id: 'item-b', label: 'B' }
      ]);

      expect(screen.getByRole('separator')).toBeInTheDocument();
      expect(screen.getAllByRole('menuitem')).toHaveLength(2);
    });
  });

  describe('Submenu items', () => {
    const subItems = [
      { key: 'sub-a', label: 'Sub A', onClick: vi.fn() },
      { key: 'sub-b', label: 'Sub B', onClick: vi.fn() }
    ];

    const submenuEntry: ContextMenuEntry = {
      kind: 'submenu',
      id: 'my-submenu',
      label: 'Parent',
      items: subItems
    };

    it('renders the parent submenu item', () => {
      renderMenu([submenuEntry]);

      expect(screen.getByText('Parent')).toBeInTheDocument();
    });

    it('does not show submenu content before hovering', () => {
      renderMenu([submenuEntry]);

      expect(screen.queryByText('Sub A')).not.toBeInTheDocument();
    });

    it('shows submenu content on mouse enter', async () => {
      renderMenu([submenuEntry]);

      const parent = screen.getByRole('menuitem');
      act(() => {
        fireEvent.mouseEnter(parent);
      });

      await waitFor(() => {
        expect(screen.getByText('Sub A')).toBeInTheDocument();
        expect(screen.getByText('Sub B')).toBeInTheDocument();
      });
    });

    it('hides submenu after mouse leave', async () => {
      renderMenu([submenuEntry]);

      const parent = screen.getByRole('menuitem');

      act(() => {
        fireEvent.mouseEnter(parent);
      });

      await waitFor(() => {
        expect(screen.getByText('Sub A')).toBeInTheDocument();
      });

      act(() => {
        fireEvent.mouseLeave(parent);
      });

      await waitFor(() => {
        expect(screen.queryByText('Sub A')).not.toBeInTheDocument();
      });
    });

    it('calls the sub-item onClick when a sub-item is clicked', async () => {
      const onClick = vi.fn();
      renderMenu([
        {
          kind: 'submenu',
          id: 'actions',
          label: 'Actions',
          items: [{ key: 'do-it', label: 'Do it', onClick }]
        }
      ]);

      const parent = screen.getByRole('menuitem');
      act(() => {
        fireEvent.mouseEnter(parent);
      });

      await waitFor(() => {
        expect(screen.getByText('Do it')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Do it'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('marks a disabled submenu parent with aria-disabled', () => {
      renderMenu([{ ...submenuEntry, disabled: true }]);

      expect(screen.getByRole('menuitem')).toHaveAttribute('aria-disabled', 'true');
    });

    it('does not show expand arrow when submenu is disabled', () => {
      renderMenu([{ ...submenuEntry, disabled: true }]);

      // The KeyboardArrowRight icon only renders when !disabled
      expect(screen.queryByTestId('KeyboardArrowRightIcon')).not.toBeInTheDocument();
    });

    it('assigns correct DOM ids to submenu parent and panel', async () => {
      renderMenu([submenuEntry]);

      expect(document.getElementById('my-submenu-menu-item')).not.toBeNull();

      const parent = screen.getByRole('menuitem');
      act(() => {
        fireEvent.mouseEnter(parent);
      });

      await waitFor(() => {
        expect(document.getElementById('my-submenu-submenu')).not.toBeNull();
      });
    });
  });

  describe('Mixed item list', () => {
    it('renders items in order', () => {
      renderMenu([
        { kind: 'item', id: 'first', label: 'First' },
        { kind: 'divider', id: 'div-1' },
        { kind: 'submenu', id: 'third', label: 'Third', items: [] },
        { kind: 'item', id: 'fourth', label: 'Fourth' }
      ]);

      const items = screen.getAllByRole('menuitem');
      expect(items[0]).toHaveTextContent('First');
      expect(items[1]).toHaveTextContent('Third');
      expect(items[2]).toHaveTextContent('Fourth');
    });
  });
});

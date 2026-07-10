import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act } from 'react';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('components/elements/ContextMenu', () => ({
  default: ({ items, children }: any) => (
    <div>
      {children}
      {items.map((item: any) => {
        if (item.kind === 'item') {
          return (
            <button key={item.id} id={item.id} onClick={item.onClick}>
              {item.label}
            </button>
          );
        }
        if (item.kind === 'divider') {
          return <hr key={item.id} />;
        }
        return null;
      })}
    </div>
  )
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

const mockDel = vi.hoisted(() => vi.fn());

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        items: {
          del: (...args: any[]) => mockDel(...args)
        }
      }
    }
  }
}));

const mockShowModal = vi.hoisted(() => vi.fn());

vi.mock('components/app/providers/ModalProvider', async () => {
  const { createContext } = await import('react');
  return {
    ModalContext: createContext({ showModal: mockShowModal, close: vi.fn(), setContent: vi.fn() })
  };
});

vi.mock('components/routes/cases/modals/RenameItemModal', () => ({
  default: () => <div id="rename-item-modal" />
}));

import CaseFolderContextMenu, { getOpenUrl } from './CaseFolderContextMenu';

const mockCase: Case = createMockCase({ case_id: 'case-1' });

const hitLeaf: Item = { id: 'id-hit', type: 'hit', value: 'hit-123', name: 'hit-item' };
const folderItem: Item = { id: 'folder-id', type: 'folder', value: 'Folder', name: 'Folder' };

const renderMenu = (props: Partial<React.ComponentPropsWithoutRef<typeof CaseFolderContextMenu>>) =>
  render(
    <CaseFolderContextMenu case={mockCase} item={hitLeaf} {...props}>
      <div id="child">child</div>
    </CaseFolderContextMenu>
  );

beforeEach(() => {
  mockDel.mockClear();
  mockDispatchApi.mockClear();
  mockShowModal.mockClear();
  mockDispatchApi.mockImplementation((p: Promise<any>) => p);
  mockDel.mockResolvedValue(mockCase);
  vi.spyOn(window, 'open').mockReturnValue(null);
});

describe('getOpenUrl', () => {
  it('resolves known leaf links and returns null for folders', () => {
    expect(getOpenUrl({ type: 'reference', value: 'https://example.com' })).toBe('https://example.com');
    expect(getOpenUrl({ type: 'hit', value: 'h1' })).toBe('/hits/h1');
    expect(getOpenUrl({ type: 'event', value: 'e1' })).toBe('/events/e1');
    expect(getOpenUrl({ type: 'case', value: 'c1' })).toBe('/cases/c1');
    expect(getOpenUrl({ type: 'folder', value: 'Folder' })).toBeNull();
  });
});

describe('CaseFolderContextMenu', () => {
  it('shows open, rename, and remove for leaf items with open URL', () => {
    renderMenu({ item: hitLeaf });
    expect(screen.getByText('page.cases.sidebar.item.open')).toBeInTheDocument();
    expect(screen.getByText('page.cases.sidebar.item.rename')).toBeInTheDocument();
    expect(screen.getByText('page.cases.sidebar.item.remove')).toBeInTheDocument();
    expect(document.querySelector('hr')).toBeInTheDocument();
  });

  it('shows rename/remove folder actions and no open action for folders', () => {
    renderMenu({ item: folderItem });
    expect(screen.queryByText('page.cases.sidebar.item.open')).not.toBeInTheDocument();
    expect(screen.getByText('page.cases.sidebar.folder.rename')).toBeInTheDocument();
    expect(screen.getByText('page.cases.sidebar.folder.remove')).toBeInTheDocument();
  });

  it('opens resolved URL in new tab', () => {
    renderMenu({ item: hitLeaf });
    act(() => {
      fireEvent.click(screen.getByText('page.cases.sidebar.item.open'));
    });
    expect(window.open).toHaveBeenCalledWith('/hits/hit-123', '_blank', 'noopener noreferrer');
  });

  it('calls showModal for rename action', () => {
    renderMenu({ item: hitLeaf });
    act(() => {
      fireEvent.click(screen.getByText('page.cases.sidebar.item.rename'));
    });
    expect(mockShowModal).toHaveBeenCalledTimes(1);
  });

  it('calls delete API with force=true for folders', async () => {
    renderMenu({ item: folderItem });
    act(() => {
      fireEvent.click(screen.getByText('page.cases.sidebar.folder.remove'));
    });
    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith('case-1', ['folder-id'], true);
    });
  });

  it('passes undefined item id through to delete API when id is missing', () => {
    renderMenu({ item: { type: 'hit', value: 'h1', name: 'hit' } });
    act(() => {
      fireEvent.click(screen.getByText('page.cases.sidebar.item.remove'));
    });
    expect(mockDel).toHaveBeenCalledWith('case-1', [undefined], false);
  });

  it('passes updated case to onUpdate after delete', async () => {
    const onUpdate = vi.fn();
    renderMenu({ item: hitLeaf, onUpdate });
    act(() => {
      fireEvent.click(screen.getByText('page.cases.sidebar.item.remove'));
    });
    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(mockCase));
  });
});

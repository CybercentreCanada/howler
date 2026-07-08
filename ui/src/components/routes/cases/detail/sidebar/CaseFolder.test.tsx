import { render, screen, waitFor } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { act, createContext } from 'react';
import { setupContextSelectorMock, setupReactRouterMock } from 'tests/mocks';
import { beforeEach, describe, expect, it, vi } from 'vitest';

setupContextSelectorMock();
setupReactRouterMock();

vi.mock('@dnd-kit/core', () => ({
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: vi.fn(), transform: null, isDragging: false }),
  useDroppable: () => ({ setNodeRef: vi.fn(), isOver: false })
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } }
}));

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockGetCase = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('api', () => ({
  default: {
    v2: {
      case: {
        get: (...args: any[]) => mockGetCase(...args),
        items: { del: vi.fn(), patch: vi.fn() }
      }
    }
  }
}));

vi.mock('./CaseFolderContextMenu', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ModalProvider', async () => ({
  ModalContext: createContext({ showModal: vi.fn(), close: vi.fn(), setContent: vi.fn() })
}));

const mockRecords = vi.hoisted(() => ({ current: {} as Record<string, any> }));
vi.mock('components/app/providers/RecordProvider', async () => ({
  RecordContext: createContext({ records: mockRecords.current })
}));

import { MemoryRouter, useParams } from 'react-router-dom';
import CaseFolder from './CaseFolder';

const makeCase = (id: string, items: Item[] = []): Case =>
  ({
    __index: 'case',
    case_id: id,
    title: `Case ${id}`,
    items,
    tasks: []
  }) as Case;

const hitItem = (name: string, value = name, id = `id-${value}`): Item => ({ id, type: 'hit', value, name });
const caseItem = (name: string, value: string, id = `id-${value}`): Item => ({ id, type: 'case', value, name });
const refItem = (name: string, value: string, id = `id-${value}`): Item => ({ id, type: 'reference', value, name });

const renderFolder = (
  props: Partial<React.ComponentPropsWithoutRef<typeof CaseFolder>> & { case: Case },
  routeId?: string
) => {
  vi.mocked(useParams).mockReturnValue({ id: routeId ?? props.case.case_id });
  return render(
    <MemoryRouter>
      <CaseFolder step={0} {...props} />
    </MemoryRouter>
  );
};

beforeEach(() => {
  mockDispatchApi.mockReset();
  mockGetCase.mockReset();
  mockRecords.current = {};
});

describe('CaseFolder', () => {
  it('builds non-reference leaf URLs from root case id and item path', () => {
    renderFolder({ case: makeCase('case-1', [hitItem('my-hit', 'hit-id', 'item-1')]) });
    const link = screen.getByText('my-hit').closest('a');
    expect(link).toHaveAttribute('href', '/cases/case-1/my-hit');
  });

  it('uses item value directly for reference href', () => {
    renderFolder({ case: makeCase('case-1', [refItem('ext', 'https://example.com')]) });
    const link = screen.getByText('ext').closest('a');
    expect(link).toHaveAttribute('href', 'https://example.com');
  });

  it('prepends parentCaseNames to non-reference item paths', () => {
    renderFolder(
      {
        case: makeCase('nested', [hitItem('page', 'page-val', 'id-page')]),
        parentCaseNames: ['Child Case']
      },
      'root-case'
    );
    const link = screen.getByText('page').closest('a');
    expect(link?.getAttribute('href')).toBe('/cases/root-case/Child Case/page');
  });

  it('fetches nested case when case leaf is clicked and renders nested leaves', async () => {
    const nestedCase = makeCase('child-case-id', [hitItem('nested-item', 'v1', 'nested-id')]);
    mockGetCase.mockReturnValue(Promise.resolve(nestedCase));
    mockDispatchApi.mockImplementation((p: Promise<any>) => p);

    renderFolder({ case: makeCase('root', [caseItem('child', 'child-case-id', 'child-id')]) });

    act(() => {
      screen.getByText('child').click();
    });

    await waitFor(() => {
      expect(mockGetCase).toHaveBeenCalledWith('child-case-id');
      expect(screen.getByText('nested-item')).toBeInTheDocument();
    });
  });

  it('uses route case id as root id for nested links', () => {
    renderFolder({ case: makeCase('nested-case', [hitItem('item', 'v', 'id-v')]) }, 'root-case');
    const link = screen.getByText('item').closest('a');
    expect(link).toHaveAttribute('href', '/cases/root-case/item');
  });
});

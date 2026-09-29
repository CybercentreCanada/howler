/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));
const gridColumnsContextToken = vi.hoisted(() => ({ name: 'grid-columns-context' }));

vi.mock('@mui/icons-material', () => ({
  Info: () => <div>info-icon</div>
}));

vi.mock('@mui/material', () => ({
  LinearProgress: () => <div>progress</div>,
  Paper: ({ children, onScroll }: any) => <div onScroll={onScroll}>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TableBody: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({ spacing: (n: number) => `${n}px`, shape: { borderRadius: 4 } })
}));

vi.mock('components/app/providers/GridColumnsProvider', () => ({
  GridColumnsContext: gridColumnsContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/elements/addons/search/SearchTotal', () => ({
  default: ({ total }: any) => <div>{`total:${total}`}</div>
}));

vi.mock('components/elements/display/features/DevelopmentBanner', () => ({
  default: () => <div>banner</div>
}));

vi.mock('components/elements/hit/grid/AddColumnModal', () => ({
  default: ({ addColumn }: any) => <button onClick={() => addColumn('field.two')}>add-column</button>
}));

vi.mock('components/elements/hit/grid/RecordTable', () => ({
  default: ({ refreshItems, query, items }: any) => (
    <div>
      <button onClick={() => refreshItems?.(query, true)}>refresh</button>
      <div>{`table:${items?.length ?? 0}`}</div>
    </div>
  )
}));

vi.mock('components/elements/record/RecordContextMenu', () => ({
  default: () => <div>context-menu</div>
}));

vi.mock('components/hooks/useRecordSelection', () => ({
  default: () => ({ onClick: vi.fn() })
}));

vi.mock('lodash-es', () => ({
  uniq: (values: string[]) => [...new Set(values)]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === recordSearchContextToken) {
      return selector({
        search: vi.fn(),
        response: { items: [{ howler: { id: 'hit-1' } }], offset: 0, rows: 25, total: 1 },
        searching: true
      });
    }
    if (context === recordContextToken) return selector({ selectedRecords: [{ howler: { id: 'hit-2' } }] });
    if (context === parameterContextToken) return selector({ query: 'status:open', selected: 'hit-1' });
    if (context === gridColumnsContextToken)
      return selector({ columns: ['field.one'], setColumns: vi.fn(), isReady: true });
    return undefined;
  }
}));

vi.mock('../QuerySettings', () => ({
  default: () => <div>query-settings</div>
}));

vi.mock('../RecordQuery', () => ({
  default: () => <div>record-query</div>
}));

vi.mock('../shared/SearchActionMenu', () => ({
  default: () => <div>search-actions</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === gridColumnsContextToken) return { columns: ['field.one'], setColumns: vi.fn(), isReady: true };
      return actual.useContext(context);
    }
  };
});

import RecordGrid from './RecordGrid';

describe('RecordGrid', () => {
  it('renders the search grid controls and empty message paths', () => {
    render(<RecordGrid />);

    expect(screen.getByText('banner')).toBeInTheDocument();
    expect(screen.getByText('record-query')).toBeInTheDocument();
    expect(screen.getByText('progress')).toBeInTheDocument();
    expect(screen.getByText('query-settings')).toBeInTheDocument();
    expect(screen.getByText('total:1')).toBeInTheDocument();
    expect(screen.getByText('table:1')).toBeInTheDocument();

    fireEvent.click(screen.getByText('add-column'));
    fireEvent.click(screen.getByText('refresh'));
  });
});

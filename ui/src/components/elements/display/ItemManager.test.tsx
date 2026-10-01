/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, Add: () => <div>add-icon</div>, Search: () => <div>search-icon</div> };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Fab: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  LinearProgress: () => <div>progress</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => false
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/lists', () => ({
  TuiList: ({ children, onSelection }: any) => <div>{children([{ id: '1', item: 'item-1' }], onSelection)}</div>
}));

vi.mock('components/elements/addons/search/SearchPagination', () => ({
  default: ({ onChange }: any) => <button onClick={() => onChange(50)}>paginate</button>
}));

vi.mock('components/elements/addons/search/SearchTotal', () => ({
  default: ({ total, pageLength, offset }: any) => <div>{`total:${total}:${pageLength}:${offset}`}</div>
}));

vi.mock('components/routes/ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('../addons/search/phrase/Phrase', () => ({
  default: ({ onKeyDown, onChange, endAdornment, value }: any) => (
    <div>
      <button onClick={() => onChange('next phrase')}>change-phrase</button>
      <button onClick={() => onKeyDown({ isEnter: true })}>enter-search</button>
      <div>{value}</div>
      {endAdornment}
    </div>
  )
}));

import ItemManager from './ItemManager';

describe('ItemManager', () => {
  it('renders search UI, totals, pagination, list items, and create action', () => {
    const onSearch = vi.fn();
    const onPageChange = vi.fn();
    const onCreate = vi.fn();
    const onSelect = vi.fn();
    const setPhrase = vi.fn();

    render(
      <ItemManager
        aboveSearch={<div>above</div>}
        afterSearch={<div>after</div>}
        belowSearch={<div>below</div>}
        searchFilters={<div>filters</div>}
        hasError={false}
        onPageChange={onPageChange}
        onSearch={onSearch}
        onCreate={onCreate}
        onSelect={onSelect}
        phrase="initial"
        renderer={(item: any, handleSelect: any) => (
          <button onClick={() => handleSelect(item, 0)}>{item[0].item ?? item.item}</button>
        )}
        response={{ total: 10, items: [{ id: '1', item: 'item-1' }], offset: 0, rows: 25, removeCount: 0 } as any}
        searching
        searchPrompt="search.prompt"
        createPrompt="create.prompt"
        setPhrase={setPhrase}
      />
    );

    expect(screen.getByText('above')).toBeInTheDocument();
    expect(screen.getByText('after')).toBeInTheDocument();
    expect(screen.getByText('below')).toBeInTheDocument();
    expect(screen.getByText('filters')).toBeInTheDocument();
    expect(screen.getByText('progress')).toBeInTheDocument();
    expect(screen.getByText('total:10:1:0')).toBeInTheDocument();
    expect(screen.getByText('create.prompt')).toBeInTheDocument();

    fireEvent.click(screen.getByText('change-phrase'));
    expect(setPhrase).toHaveBeenCalledWith('next phrase');

    fireEvent.click(screen.getByText('enter-search'));
    fireEvent.click(screen.getByText('search-icon'));
    expect(onSearch).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByText('paginate'));
    expect(onPageChange).toHaveBeenCalledWith(50);

    fireEvent.click(screen.getByText('item-1'));
    expect(onSelect).toHaveBeenCalled();

    fireEvent.click(screen.getByText('create.prompt'));
    expect(onCreate).toHaveBeenCalled();
  });
});

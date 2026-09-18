/// <reference types="vitest" />
import dayjs from 'dayjs';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockNavigate = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockLoad = vi.hoisted(() => vi.fn());
const mockRequest = vi.hoisted(() => vi.fn());
const listMethodContextToken = vi.hoisted(() => ({ name: 'list-method-context' }));

let searchParamsValue = new URLSearchParams();
let responseValue: any = {
  total: 1,
  items: [{ case_id: 'case-1', owner: 'demo' }]
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Topic: () => <div>topic-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    v2: {
      fuzzy: {
        post: 'case-search'
      }
    }
  }
}));

vi.mock('components/app/providers/SearchResponseProvider', () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
  createSearchResponseContext: () => ({}),
  useSearchResponseContext: () => ({
    response: responseValue,
    request: mockRequest
  })
}));

vi.mock('components/elements/addons/lists', () => ({
  TuiListProvider: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/lists/TuiListProvider', () => ({
  TuiListMethodContext: listMethodContextToken
}));

vi.mock('components/elements/display/ItemManager', () => ({
  default: (props: any) => (
    <div>
      <button onClick={() => props.onSearch()}>search</button>
      <button onClick={() => props.onPageChange(30)}>page</button>
      <button onClick={() => props.onSelect({ id: 'case-1' })}>select</button>
      <div>{props.searchFilters}</div>
      {props.response?.items?.map((item: any) => (
        <div key={item.case_id}>{props.renderer({ item: { item } }, () => 'card')}</div>
      ))}
    </div>
  )
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [25]
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('./search/CaseAssigneeFilter', () => ({
  default: ({ onChange }: any) => <button onClick={() => onChange(['Alice Example'])}>assignee-filter</button>
}));

vi.mock('./search/CaseDateFilter', () => ({
  default: ({ onChange, onCustomStartChange, onCustomEndChange }: any) => (
    <div>
      <button onClick={() => onChange('date.range.1.day')}>date-range</button>
      <button onClick={() => onChange('date.range.custom')}>date-custom</button>
      <button onClick={() => onCustomStartChange(dayjs('2026-01-01T00:00:00.000Z'))}>custom-start</button>
      <button onClick={() => onCustomEndChange(dayjs('2026-01-02T00:00:00.000Z'))}>custom-end</button>
    </div>
  )
}));

vi.mock('./search/CaseStatusFilter', () => ({
  default: ({ onChange }: any) => <button onClick={() => onChange(['open', 'triaged'])}>status-filter</button>
}));

vi.mock('../../elements/case/CaseCard', () => ({
  default: ({ case: caseItem, className }: any) => <div>{`${caseItem.case_id}:${className}`}</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === listMethodContextToken) {
        return { load: mockLoad };
      }
      return actual.useContext(context);
    }
  };
});

import Cases from './Cases';

describe('Cases', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    responseValue = {
      total: 1,
      items: [{ case_id: 'case-1', owner: 'demo' }]
    };
    mockNavigate.mockReset();
    mockSetSearchParams.mockReset();
    mockLoad.mockReset();
    mockRequest.mockReset();
  });

  it('searches cases, applies filters, paginates, and navigates to selected cases', async () => {
    render(<Cases />);

    await waitFor(() =>
      expect(mockRequest).toHaveBeenCalledWith('case-search', {
        query: '*',
        filters: [],
        rows: 25,
        offset: 0,
        indexes: ['case']
      })
    );
    expect(mockLoad).toHaveBeenCalledWith([expect.objectContaining({ id: 'case-1' })]);

    fireEvent.click(screen.getByText('status-filter'));
    await waitFor(() =>
      expect(mockRequest).toHaveBeenLastCalledWith('case-search', {
        query: '*',
        filters: ['status:("open" OR "triaged")'],
        rows: 25,
        offset: 0,
        indexes: ['case']
      })
    );

    fireEvent.click(screen.getByText('assignee-filter'));
    await waitFor(() =>
      expect(mockRequest.mock.calls.at(-1)[1].filters).toEqual(
        expect.arrayContaining(['(participants:"Alice Example" OR tasks.assignment:"Alice Example")'])
      )
    );

    fireEvent.click(screen.getByText('date-range'));
    await waitFor(() =>
      expect(mockRequest.mock.calls.at(-1)[1].filters).toEqual(
        expect.arrayContaining(['created:[now-1d/d TO now]'])
      )
    );

    fireEvent.click(screen.getByText('date-custom'));
    fireEvent.click(screen.getByText('custom-start'));
    fireEvent.click(screen.getByText('custom-end'));
    await waitFor(() =>
      expect(mockRequest.mock.calls.at(-1)[1].filters.some((entry: string) => entry.startsWith('created:['))).toBe(true)
    );

    fireEvent.click(screen.getByText('page'));
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('select'));
    expect(mockNavigate).toHaveBeenCalledWith('/cases/case-1');
  });
});

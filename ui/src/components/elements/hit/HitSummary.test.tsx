/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowErrorMessage = vi.hoisted(() => vi.fn());
const mockSetQuery = vi.hoisted(() => vi.fn());
const mockGetFilters = vi.hoisted(() => vi.fn().mockResolvedValue(['status:open']));
const mockGetMatchingTemplate = vi.hoisted(() => vi.fn());

const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));

let fieldContextValue: any;
let parameterContextValue: any;
let recordSearchContextValue: any;

vi.mock('@mui/icons-material', () => ({
  Analytics: () => <div>analytics-icon</div>,
  InfoOutlined: () => <div>info-icon</div>
}));

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Autocomplete: ({ onChange, renderInput }: any) => (
    <div>
      {renderInput({})}
      <button onClick={() => onChange?.(null, ['custom.field'])}>add-custom-field</button>
    </div>
  ),
  Box: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Chip: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  CircularProgress: () => <div>loading</div>,
  Divider: () => <div>divider</div>,
  Fade: ({ children }: any) => <div>{children}</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  LinearProgress: () => <div>progress</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    search: {
      facet: {
        hit: {
          post: (body: any) => body
        }
      }
    }
  }
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingTemplate: mockGetMatchingTemplate })
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: (key: string, fallback: any) => [key === 'SHOW_HIT_SUMMARY_GRAPH' ? true : fallback]
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage })
}));

vi.mock('lodash-es', () => ({
  isEmpty: (value: any) =>
    value == null || (Array.isArray(value) ? value.length === 0 : typeof value === 'object' ? Object.keys(value).length === 0 : !value)
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === parameterContextToken) return selector(parameterContextValue);
    if (context === recordSearchContextToken) return selector(recordSearchContextValue);
    return undefined;
  }
}));

vi.mock('utils/constants', () => ({
  StorageKey: {
    PAGE_COUNT: 'PAGE_COUNT',
    SHOW_HIT_SUMMARY_GRAPH: 'SHOW_HIT_SUMMARY_GRAPH'
  }
}));

vi.mock('utils/typeUtils', () => ({
  isHit: (item: any) => item?.__index === 'hit'
}));

vi.mock('utils/utils', () => ({
  getTimeRange: (values: string[]) => [values[0], values[values.length - 1]],
  notNil: (value: any) => value != null
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === fieldContextToken) return fieldContextValue;
      return actual.useContext(context);
    }
  };
});

vi.mock('../PluginChip', () => ({
  default: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>
}));

vi.mock('./aggregate/HitGraph', () => ({
  default: () => <div>hit-graph</div>
}));

import HitSummary from './HitSummary';

describe('HitSummary', () => {
  beforeEach(() => {
    fieldContextValue = {
      hitFields: [{ key: 'severity', type: 'keyword' }, { key: 'event.created', type: 'date' }]
    };
    parameterContextValue = {
      query: 'status:open',
      setQuery: mockSetQuery,
      views: []
    };
    recordSearchContextValue = {
      searching: false,
      error: '',
      getFilters: mockGetFilters
    };
    mockDispatchApi.mockReset();
    mockShowErrorMessage.mockReset();
    mockSetQuery.mockReset();
    mockGetFilters.mockClear();
    mockGetMatchingTemplate.mockReset();
  });

  it('aggregates template keys, supports ad hoc fields, and updates the search query from results', async () => {
    mockGetMatchingTemplate
      .mockResolvedValueOnce({ analytic: 'Analytic A', detection: 'Rule A', keys: ['severity', 'howler.id'] })
      .mockResolvedValueOnce({ analytic: 'Analytic A', detection: 'Rule B', keys: ['event.created'] });
    mockDispatchApi
      .mockResolvedValueOnce({
        severity: { high: 2, low: 1 },
        'event.created': { '2026-01-01T00:00:00Z': 1, '2026-01-02T00:00:00Z': 1 }
      })
      .mockResolvedValueOnce({
        severity: { high: 2 },
        'event.created': { '2026-01-01T00:00:00Z': 1, '2026-01-02T00:00:00Z': 1 },
        'custom.field': { custom: 3 }
      });

    render(
      <HitSummary
        response={{
          items: [
            { __index: 'hit', howler: { id: 'hit-1' } },
            { __index: 'hit', howler: { id: 'hit-2' } }
          ]
        } as any}
      />
    );

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        {
          fields: ['severity', 'event.created'],
          query: 'status:open',
          rows: 25,
          filters: ['status:open']
        },
        { throwError: false, logError: true, showError: false }
      )
    );
    expect(screen.getByText('hit-graph')).toBeInTheDocument();
    expect(screen.getByText('severity')).toBeInTheDocument();

    fireEvent.click(screen.getByText('high (2)'));
    expect(mockSetQuery).toHaveBeenCalledWith('severity:"high"');

    fireEvent.click(screen.getByText('add-custom-field'));
    fireEvent.click(screen.getByText('button.aggregate'));

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenLastCalledWith(
        {
          fields: ['custom.field'],
          query: 'status:open',
          rows: 25,
          filters: ['status:open']
        },
        { throwError: false, logError: true, showError: false }
      )
    );
    expect(screen.getByText('custom.field')).toBeInTheDocument();
  });

  it('shows the empty state and reports aggregation failures', async () => {
    mockGetMatchingTemplate.mockResolvedValueOnce({ analytic: 'Analytic A', detection: 'Rule A', keys: ['severity'] });
    mockDispatchApi.mockRejectedValueOnce(new Error('aggregate failed'));

    render(<HitSummary response={{ items: [{ __index: 'hit', howler: { id: 'hit-1' } }] } as any} />);

    await waitFor(() => expect(mockShowErrorMessage).toHaveBeenCalledWith('aggregate failed'));
    expect(screen.getByText('hit.summary.aggregate.nokeys.title')).toBeInTheDocument();
    expect(screen.getByText('hit.summary.aggregate.nokeys.description')).toBeInTheDocument();
  });
});

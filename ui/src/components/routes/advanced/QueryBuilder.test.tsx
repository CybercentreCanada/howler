/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetHitFields = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockLucenePost = vi.hoisted(() => vi.fn());
const mockFacetPost = vi.hoisted(() => vi.fn());
const mockGroupedPost = vi.hoisted(() => vi.fn());
const mockExplainPost = vi.hoisted(() => vi.fn());
const mockEqlPost = vi.hoisted(() => vi.fn());
const mockSigmaPost = vi.hoisted(() => vi.fn());
const mockSetValue = vi.hoisted(() => vi.fn());
const mockDispose = vi.hoisted(() => vi.fn());
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));

let fieldContextValue: any;

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => ({
    KeyMod: { CtrlCmd: 1 },
    KeyCode: { Enter: 2 },
    editor: {
      addEditorAction: () => ({ dispose: mockDispose }),
      getModels: () => [{ setValue: mockSetValue }]
    }
  })
}));

vi.mock('@mui/icons-material', () => ({
  OpenInNew: () => <div>open-icon</div>,
  PlayArrowOutlined: () => <div>play-icon</div>
}));

vi.mock('@mui/material', () => ({
  Alert: ({ children }: any) => <div>{children}</div>,
  AlertTitle: ({ children }: any) => <div>{children}</div>,
  Autocomplete: ({ options, onChange, renderInput, multiple }: any) => (
    <div>
      {renderInput({})}
      {options.map((option: any) => (
        <button key={String(option)} onClick={() => onChange?.(null, multiple ? [option] : option)}>
          {String(option)}
        </button>
      ))}
    </div>
  ),
  Box: ({ children, onMouseDown }: any) => <div onMouseDown={onMouseDown}>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  Checkbox: ({ checked, onChange }: any) => (
    <button onClick={() => onChange?.(null, !checked)}>{checked ? 'checked' : 'unchecked'}</button>
  ),
  Chip: ({ label }: any) => <div>{label}</div>,
  CircularProgress: () => <div>loading</div>,
  FormControlLabel: ({ control, label }: any) => <div>{control}{label}</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  ListItemText: ({ primary, secondary }: any) => <div>{primary}{secondary}</div>,
  Slider: ({ onChange }: any) => <button onClick={() => onChange?.(null, 3)}>rows-slider</button>,
  Stack: ({ children, onKeyDown }: any) => <div onKeyDown={onKeyDown}>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useMediaQuery: () => false,
  useTheme: () => ({ palette: { divider: '#ddd', background: { paper: '#fff' } }, shape: { borderRadius: 4 } })
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>,
  parseEvent: (event: any) => ({ isCtrl: !!event.ctrlKey, isEnter: event.key === 'Enter' })
}));

vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: mockLucenePost,
        explain: { post: mockExplainPost },
        eql: { post: mockEqlPost },
        sigma: { post: mockSigmaPost }
      },
      facet: {
        hit: { post: mockFacetPost }
      },
      grouped: {
        hit: { post: mockGroupedPost }
      }
    }
  }
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/elements/addons/buttons/CustomButton', () => ({
  default: ({ children, onClick, disabled, to }: any) => <button onClick={onClick} disabled={disabled} data-to={to}>{children}</button>
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/display/json/JSONViewer', () => ({
  default: ({ data, collapse }: any) => <div>{`json:${JSON.stringify(data)}:${String(collapse)}`}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>
}));

vi.mock('utils/stringUtils', () => ({
  sanitizeMultilineLucene: (value: string) => value.replace(/\s+/g, ' ').trim()
}));

vi.mock('uuid', () => ({
  v4: () => 'uuid-value'
}));

vi.mock('./QueryEditor', () => ({
  default: ({ query, setQuery }: any) => (
    <div>
      <div>{query}</div>
      <button onClick={() => setQuery('updated query')}>set-query</button>
    </div>
  )
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

import QueryBuilder from './QueryBuilder';

describe('QueryBuilder', () => {
  beforeEach(() => {
    fieldContextValue = {
      hitFields: [{ key: 'howler.id' }, { key: 'event.id' }],
      getHitFields: mockGetHitFields
    };
    mockGetHitFields.mockClear();
    mockLucenePost.mockReset().mockResolvedValue({ items: [{ id: 1 }] });
    mockFacetPost.mockReset().mockResolvedValue({ items: [{ value: 'x' }] });
    mockGroupedPost.mockReset().mockResolvedValue({ items: [{ value: 'g' }] });
    mockExplainPost.mockReset().mockResolvedValue({ explanation: true });
    mockEqlPost.mockReset().mockResolvedValue({ items: [{ id: 2 }] });
    mockSigmaPost.mockReset().mockResolvedValue({ items: [{ id: 3 }] });
    mockSetValue.mockReset();
    mockDispose.mockReset();
  });

  it('executes lucene, facet, groupby, and explain searches', async () => {
    render(<QueryBuilder />);

    await waitFor(() => expect(mockGetHitFields).toHaveBeenCalled());

    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockLucenePost).toHaveBeenCalledWith({ query: '# Match any howler.id value howler.id:* AND # Hits must be open howler.status:open', fl: undefined, rows: 5 }));

    fireEvent.click(screen.getByText('facet'));
    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockFacetPost).toHaveBeenCalledWith({
      query: '# Match any howler.id value howler.id:* AND # Hits must be open howler.status:open',
      rows: 5,
      fields: ['howler.id']
    }));

    fireEvent.click(screen.getByText('groupby'));
    expect(screen.getByText('route.actions.execute')).toBeDisabled();
    fireEvent.click(screen.getAllByText('howler.id')[0]!);
    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockGroupedPost).toHaveBeenCalledWith('howler.id', {
      query: '# Match any howler.id value howler.id:* AND # Hits must be open howler.status:open',
      fl: undefined,
      rows: 5
    }));

    fireEvent.click(screen.getByText('explain'));
    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockExplainPost).toHaveBeenCalledWith({
      query: '# Match any howler.id value howler.id:* AND # Hits must be open howler.status:open'
    }));
  });

  it('switches query types, resets monaco content, and executes eql and sigma searches', async () => {
    render(<QueryBuilder />);

    fireEvent.click(screen.getByText('rows-slider'));
    fireEvent.click(screen.getByText('eql'));
    await waitFor(() => expect(mockSetValue).toHaveBeenCalled());
    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockEqlPost).toHaveBeenCalledWith({
      eql_query: '# Match any howler.id value howler.id:* AND # Hits must be open howler.status:open',
      fl: undefined,
      rows: 50
    }));

    fireEvent.click(screen.getByText('yaml'));
    fireEvent.click(screen.getByText('set-query'));
    fireEvent.click(screen.getByText('route.actions.execute'));
    await waitFor(() => expect(mockSigmaPost).toHaveBeenCalledWith(
      expect.objectContaining({
        sigma: 'updated query',
        fl: undefined,
        rows: 50
      })
    ));
  });

  it('shows errors when a search fails', async () => {
    mockLucenePost.mockRejectedValueOnce(new Error('search failed'));

    render(<QueryBuilder />);

    fireEvent.click(screen.getByText('route.actions.execute'));

    await waitFor(() => expect(screen.getByText('route.advanced.error')).toBeInTheDocument());
    expect(screen.getByText('search failed')).toBeInTheDocument();
  });
});

/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockTriggerSearch = vi.hoisted(() => vi.fn());
const mockOnChange = vi.hoisted(() => vi.fn());
const mockSetValue = vi.hoisted(() => vi.fn());
const mockActionDispose = vi.hoisted(() => vi.fn());
const mockKeybindingDispose = vi.hoisted(() => vi.fn());
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));

let parameterContextValue: any;
let recordSearchContextValue: any;
let locationValue = { search: '' };

vi.mock('@monaco-editor/react', () => ({
  useMonaco: () => ({
    KeyMod: { CtrlCmd: 1 },
    KeyCode: { Enter: 2 },
    editor: {
      addEditorAction: () => ({ dispose: mockActionDispose }),
      addKeybindingRule: () => ({ dispose: mockKeybindingDispose })
    }
  })
}));

vi.mock('@mui/icons-material', () => ({
  Clear: () => <div>clear-icon</div>,
  Height: () => <div>height-icon</div>,
  History: () => <div>history-icon</div>,
  Search: () => <div>search-icon</div>
}));

vi.mock('@mui/material', () => ({
  Badge: ({ children }: any) => <div>{children}</div>,
  Box: ({ children, onMouseDown }: any) => <div onMouseDown={onMouseDown}>{children}</div>,
  Card: ({ children, onKeyDown }: any) => <div onKeyDown={onKeyDown}>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  alpha: () => 'rgba(0,0,0,0.5)',
  useTheme: () => ({
    spacing: (n: number) => `${n}px`,
    palette: { text: { primary: '#111' }, divider: '#ddd', background: { paper: '#fff' } },
    transitions: { create: () => 'transition' }
  })
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/elements/addons/buttons/CustomIconButton', () => ({
  default: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>
}));

vi.mock('components/routes/advanced/QueryEditor', () => ({
  default: ({ query, setQuery, onMount }: any) => {
    return (
      <div>
        <div>{query}</div>
        <button onClick={() => setQuery('line1\nline2')}>set-multiline-query</button>
        <button onClick={() => onMount?.({ createContextKey: vi.fn() })}>mount-editor</button>
      </div>
    );
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === parameterContextToken) return selector(parameterContextValue);
    if (context === recordSearchContextToken) return selector(recordSearchContextValue);
    return undefined;
  }
}));

vi.mock('utils/constants', () => ({
  DEFAULT_QUERY: '*:*'
}));

vi.mock('utils/stringUtils', () => ({
  sanitizeMultilineLucene: (value: string) => value.replace(/\n/g, ' ').trim()
}));

import RecordQuery from './RecordQuery';

describe('RecordQuery', () => {
  beforeEach(() => {
    parameterContextValue = { query: 'status:open' };
    recordSearchContextValue = { fzfSearch: true };
    locationValue = { search: '?query=status:open' };
    mockTriggerSearch.mockReset();
    mockOnChange.mockReset();
    mockSetValue.mockReset();
    mockActionDispose.mockReset();
    mockKeybindingDispose.mockReset();
    window.history.replaceState({}, '', '/?query=status:open');
  });

  it('reports dirty state, toggles multiline, clears the query, and triggers searches', async () => {
    render(<RecordQuery triggerSearch={mockTriggerSearch} onChange={mockOnChange} />);
    fireEvent.click(screen.getByText('mount-editor'));

    await waitFor(() => expect(mockOnChange).toHaveBeenCalledWith('status:open', false));
    expect(screen.getByText('history-icon')).toBeInTheDocument();

    fireEvent.click(screen.getByText('height-icon'));
    fireEvent.click(screen.getByText('set-multiline-query'));

    await waitFor(() => expect(mockOnChange).toHaveBeenLastCalledWith('line1\nline2', true));

    fireEvent.click(screen.getByText('search-icon'));
    expect(mockTriggerSearch).toHaveBeenCalledWith('line1 line2');

    fireEvent.click(screen.getByText('clear-icon'));
    await waitFor(() => expect(mockOnChange).toHaveBeenLastCalledWith('*:*', true));
  });

  it('disables actions and updates when the saved query changes', async () => {
    const { rerender, unmount } = render(
      <RecordQuery triggerSearch={mockTriggerSearch} onChange={mockOnChange} searching disabled compact />
    );
    fireEvent.click(screen.getByText('mount-editor'));

    expect(screen.getAllByRole('button').filter(button => button.hasAttribute('disabled')).length).toBeGreaterThanOrEqual(3);

    parameterContextValue.query = 'priority:high';
    locationValue = { search: '' };
    rerender(<RecordQuery triggerSearch={mockTriggerSearch} onChange={mockOnChange} />);

    await waitFor(() => expect(mockOnChange).toHaveBeenLastCalledWith('priority:high', false));

    unmount();
    expect(mockActionDispose).toHaveBeenCalled();
    expect(mockKeybindingDispose).toHaveBeenCalled();
  });
});

/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockShowSuccessMessage = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());
const mockWithConfirmDeleteModal = vi.hoisted(() => vi.fn((cb: () => Promise<void>) => cb()));
const mockGetOverviews = vi.hoisted(() => vi.fn());
const mockOverviewPut = vi.hoisted(() => vi.fn((id: string, content: string) => ({ id, content })));
const mockOverviewDelete = vi.hoisted(() => vi.fn((id: string) => ({ id })));
const modalContextToken = vi.hoisted(() => ({ name: 'modal-context' }));
const overviewContextToken = vi.hoisted(() => ({ name: 'overview-context' }));

let searchParamsValue = new URLSearchParams('analytic=Alpha');

vi.mock('@mui/icons-material', () => ({
  Check: () => <div>check-icon</div>,
  DarkMode: () => <div>dark-icon</div>,
  Delete: () => <div>delete-icon</div>,
  WbSunny: () => <div>light-icon</div>
}));

vi.mock('@mui/material', () => ({
  Autocomplete: ({ options, value, onChange, renderInput }: any) => (
    <div>
      {renderInput({})}
      <button onClick={() => onChange(null, options[0] ?? null)}>{typeof value === 'object' ? value?.name : value || 'empty'}</button>
    </div>
  ),
  Box: ({ children, onMouseDown, onKeyDown }: any) => <div onMouseDown={onMouseDown} onKeyDown={onKeyDown}>{children}</div>,
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  CircularProgress: () => <div>loading</div>,
  Divider: () => <div>divider</div>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  LinearProgress: () => <div>progress</div>,
  Stack: ({ children, onKeyDown }: any) => <div onKeyDown={onKeyDown}>{children}</div>,
  TextField: ({ label, size }: any) => <div>{label ?? size}</div>,
  ThemeProvider: ({ children }: any) => <div>{children}</div>,
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, 'dark')}>switch-dark</button>
      {children}
    </div>
  ),
  Tooltip: ({ children }: any) => <>{children}</>,
  useTheme: () => ({ palette: { divider: '#ddd' }, shape: { borderRadius: 4 } })
}));

vi.mock('@tui/core', () => ({
  AppInfoPanel: ({ i18nKey }: any) => <div>{i18nKey}</div>,
  PageCenter: ({ children }: any) => <div>{children}</div>,
  useAppTheme: () => ({ current: 'default', optionsOverride: {}, mode: 'light' }),
  useAppThemeBuilder: () => () => ({
    lightTheme: { palette: { background: { default: '#fff' }, text: { primary: '#111' } } },
    darkTheme: { palette: { background: { default: '#000' }, text: { primary: '#eee' } } }
  })
}));

vi.mock('api', () => ({
  default: {
    search: {
      analytic: { post: (body: any) => body },
      hit: { post: (body: any) => body }
    },
    overview: {
      put: mockOverviewPut,
      del: mockOverviewDelete
    }
  }
}));

vi.mock('components/app/providers/ModalProvider', () => ({
  ModalContext: modalContextToken
}));

vi.mock('components/app/providers/OverviewProvider', () => ({
  OverviewContext: overviewContextToken
}));

vi.mock('components/elements/hit/HitOverview', () => ({
  default: ({ content, hit }: any) => <div>{`${content}|${hit?.howler?.analytic}|${hit?.howler?.detection ?? ''}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showSuccessMessage: mockShowSuccessMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === modalContextToken) return { withConfirmDeleteModal: mockWithConfirmDeleteModal };
      if (context === overviewContextToken) return { getOverviews: mockGetOverviews };
      return actual.useContext(context);
    }
  };
});

vi.mock('utils/exampleHit', () => ({
  getExampleHit: () => ({ howler: { analytic: 'example', detection: 'fallback' } })
}));

vi.mock('utils/stringUtils', () => ({
  sanitizeLuceneQuery: (value: string) => value
}));

vi.mock('./startingTemplate', () => ({
  useStartingTemplate: () => 'starting-template'
}));

vi.mock('../../elements/MarkdownEditor', () => ({
  default: ({ content, setContent }: any) => (
    <div>
      <div>{content}</div>
      <button onClick={() => setContent('updated-content')}>edit-content</button>
    </div>
  )
}));

import OverviewViewer from './OverviewViewer';

describe('OverviewViewer', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams('analytic=Alpha');
    mockDispatchApi.mockReset();
    mockDispatchApi.mockResolvedValue({ items: [] } as any);
    mockShowSuccessMessage.mockReset();
    mockSetSearchParams.mockReset();
    mockWithConfirmDeleteModal.mockClear();
    mockGetOverviews.mockReset();
    mockOverviewPut.mockClear();
    mockOverviewDelete.mockClear();
  });

  it('loads an overview, saves edited content, and deletes it', async () => {
    mockGetOverviews.mockResolvedValueOnce([{ overview_id: 'ov-1', analytic: 'Alpha', content: 'stored-content' }]);
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request?.query === 'analytic_id:*') return { items: [{ name: 'Alpha', detections: ['det-1'] }] };
      if (request?.fl === '*') return { items: [] };
      if (request?.content === 'updated-content') return { overview_id: 'ov-1', analytic: 'Alpha', content: 'updated-content' };
      return {};
    });

    render(<OverviewViewer />);

    await waitFor(() => expect(screen.getByText('stored-content|Alpha|ANY')).toBeInTheDocument());
    expect(mockSetSearchParams).toHaveBeenCalled();

    fireEvent.click(screen.getByText('edit-content'));
    fireEvent.click(screen.getByText('button.save'));

    await waitFor(() => expect(mockOverviewPut).toHaveBeenCalledWith('ov-1', 'updated-content'));

    fireEvent.click(screen.getByText('button.delete'));
    await waitFor(() => expect(mockOverviewDelete).toHaveBeenCalledWith('ov-1'));
    expect(mockShowSuccessMessage).toHaveBeenCalledWith('route.overviews.manager.delete.success');
  });

  it('renders the selection prompt when no analytic is selected', async () => {
    searchParamsValue = new URLSearchParams();
    mockGetOverviews.mockResolvedValueOnce([]);
    mockDispatchApi.mockImplementation(async (request: any) => {
      if (request?.query === 'analytic_id:*') return { items: [] };
      if (request?.fl === '*') return { items: [] };
      return {};
    });

    render(<OverviewViewer />);

    await waitFor(() => expect(screen.getByText('route.overviews.select')).toBeInTheDocument());
  });
});

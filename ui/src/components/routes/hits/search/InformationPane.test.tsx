/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockEmit = vi.hoisted(() => vi.fn());
const mockGetMatchingOverview = vi.hoisted(() => vi.fn());
const mockGetMatchingDossiers = vi.hoisted(() => vi.fn());
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn());
const mockGetRecord = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockOnClose = vi.hoisted(() => vi.fn());

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const socketContextToken = vi.hoisted(() => ({ name: 'socket-context' }));

let parameterContextValue: any;
let recordContextValue: any;
let socketContextValue: any;
let locationValue = { pathname: '/hits' };

vi.mock('@iconify/react', () => ({
  Icon: () => <div>icon</div>
}));

vi.mock('@mui/icons-material', () => ({
  Clear: () => <div>clear-icon</div>,
  Code: () => <div>code-icon</div>,
  Comment: () => <div>comment-icon</div>,
  DataObject: () => <div>data-icon</div>,
  History: () => <div>history-icon</div>,
  LinkSharp: () => <div>link-icon</div>,
  OpenInNew: () => <div>open-icon</div>,
  QueryStats: () => <div>query-icon</div>
}));

vi.mock('@mui/material', () => ({
  Badge: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  Divider: () => <div>divider</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tab: ({ value, onClick }: any) => <button role="tab" onClick={onClick}>{value}</button>,
  Tabs: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  useTheme: () => ({ palette: { background: { paper: '#fff', default: '#fff' }, divider: '#ddd' }, spacing: () => 0 })
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({
    getMatchingOverview: mockGetMatchingOverview,
    getMatchingDossiers: mockGetMatchingDossiers,
    getMatchingAnalytic: mockGetMatchingAnalytic
  })
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/SocketProvider', () => ({
  SocketContext: socketContextToken
}));

vi.mock('components/elements/addons/buttons/CustomIconButton', () => ({
  default: ({ children, onClick, tooltip, href, route }: any) => (
    <button onClick={onClick} data-href={href} data-route={route}>
      {tooltip ?? children}
    </button>
  )
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBox', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBoxContent', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/layout/vsbox/VSBoxHeader', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/addons/search/phrase/Phrase', () => ({
  default: ({ value, onChange, error, label, endAdornment }: any) => (
    <div>
      <label>
        {label}
        <input aria-label={label} value={value} onChange={e => onChange(e.target.value)} />
      </label>
      <div>{error ? 'phrase-error' : 'phrase-ok'}</div>
      {endAdornment}
    </div>
  )
}));

vi.mock('components/elements/display/icons/SocketBadge', () => ({
  default: () => <div>socket-badge</div>
}));

vi.mock('components/elements/display/json/JSONViewer', () => ({
  default: ({ data, filter }: any) => <div>{`json:${JSON.stringify(data)}:${filter}`}</div>
}));

vi.mock('components/elements/hit/HitActions', () => ({
  default: () => <div>hit-actions</div>
}));

vi.mock('components/elements/hit/HitBanner', () => ({
  default: () => <div>hit-banner</div>
}));

vi.mock('components/elements/hit/HitLabels', () => ({
  default: () => <div>hit-labels</div>
}));

vi.mock('components/elements/hit/HitLinks', () => ({
  default: ({ dossiers, analytic }: any) => <div>{`hit-links:${analytic?.analytic_id ?? ''}:${dossiers.length}`}</div>
}));

vi.mock('components/elements/hit/HitOutline', () => ({
  default: () => <div>hit-outline</div>
}));

vi.mock('components/elements/hit/HitOverview', () => ({
  default: ({ hit }: any) => <div>{`hit-overview:${hit?.howler?.id ?? ''}`}</div>
}));

vi.mock('components/elements/hit/HitSummary', () => ({
  default: () => <div>hit-summary</div>
}));

vi.mock('components/elements/ObjectDetails', () => ({
  default: ({ obj }: any) => <div>{`details:${obj.__index ?? 'none'}`}</div>
}));

vi.mock('components/elements/record/RecordComments', () => ({
  default: () => <div>record-comments</div>
}));

vi.mock('components/elements/record/RecordRelated', () => ({
  default: () => <div>record-related</div>
}));

vi.mock('components/elements/record/RecordWorklog', () => ({
  default: () => <div>record-worklog</div>
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: () => ['Analyst']
}));

vi.mock('components/routes/ErrorBoundary', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('../shared/PluginViewing', () => ({
  default: () => <div>plugin-viewing</div>
}));

vi.mock('../view/LeadRenderer', () => ({
  default: ({ lead }: any) => <div>{`lead:${lead.label.en}`}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === parameterContextToken) return selector(parameterContextValue);
    if (context === recordContextToken) return selector(recordContextValue);
    return undefined;
  }
}));

vi.mock('utils/recordFunctions', () => ({
  getUserList: () => new Set(['analyst'])
}));

vi.mock('utils/stringUtils', () => ({
  validateRegex: (value: string) => value !== '['
}));

vi.mock('utils/typeUtils', () => ({
  isHit: (record: any) => record?.__index === 'hit'
}));

vi.mock('utils/utils', () => ({
  tryParse: (value: string) => `parsed:${value}`
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === socketContextToken) return socketContextValue;
      return actual.useContext(context);
    }
  };
});

import InformationPane from './InformationPane';

describe('InformationPane', () => {
  beforeEach(() => {
    parameterContextValue = { selected: 'hit-1' };
    recordContextValue = {
      getRecord: mockGetRecord,
      records: {
        'hit-1': {
          __index: 'hit',
          howler: {
            id: 'hit-1',
            data: ['{"source":"data"}'],
            comment: [{}],
            dossier: [{ label: { en: 'Local lead', fr: 'Piste locale' } }]
          }
        }
      }
    };
    socketContextValue = { emit: mockEmit, open: true };
    locationValue = { pathname: '/hits' };
    mockEmit.mockReset();
    mockGetMatchingOverview.mockReset().mockResolvedValue({ content: 'overview' });
    mockGetMatchingDossiers.mockReset().mockResolvedValue([
      { leads: [{ label: { en: 'External lead', fr: 'Piste externe' } }] }
    ]);
    mockGetMatchingAnalytic.mockReset().mockResolvedValue({ analytic_id: 'analytic-1' });
    mockGetRecord.mockReset().mockResolvedValue(undefined);
    mockOnClose.mockReset();
  });

  it('renders hit content, switches tabs, filters json views, and emits socket events', async () => {
    const { unmount } = render(<InformationPane onClose={mockOnClose} />);

    await waitFor(() => expect(mockGetMatchingOverview).toHaveBeenCalled());
    expect(mockEmit).toHaveBeenCalledWith({ broadcast: false, action: 'viewing', id: 'hit-1' });
    expect(screen.getByText('plugin-viewing')).toBeInTheDocument();
    expect(screen.getByText('hit-links:analytic-1:1')).toBeInTheDocument();
    expect(screen.getByText('hit-actions')).toBeInTheDocument();
    expect(screen.getByText('details:hit')).toBeInTheDocument();

    fireEvent.click(screen.getByText('overview'));
    await waitFor(() => expect(screen.getByText('hit-overview:hit-1')).toBeInTheDocument());

    fireEvent.click(screen.getByText('lead:0'));
    await waitFor(() => expect(screen.getByText('lead:Local lead')).toBeInTheDocument());

    fireEvent.click(screen.getByText('external-lead:0:0'));
    await waitFor(() => expect(screen.getByText('lead:External lead')).toBeInTheDocument());

    fireEvent.click(screen.getByText('data'));
    await waitFor(() => expect(screen.getByText(/json:\["parsed:/)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('json.viewer.search.label'), { target: { value: '[' } });
    expect(screen.getByText('phrase-error')).toBeInTheDocument();
    fireEvent.click(screen.getByText('clear-icon'));
    expect(screen.getByText('phrase-ok')).toBeInTheDocument();

    fireEvent.click(screen.getByText('raw'));
    await waitFor(() => expect(screen.getByText(/json:\{"__index":"hit"/)).toBeInTheDocument());

    fireEvent.click(screen.getByText('comments'));
    await waitFor(() => expect(screen.getByText('record-comments')).toBeInTheDocument());

    fireEvent.click(screen.getByText('worklog'));
    await waitFor(() => expect(screen.getByText('record-worklog')).toBeInTheDocument());

    fireEvent.click(screen.getByText('related'));
    await waitFor(() => expect(screen.getByText('record-related')).toBeInTheDocument());

    fireEvent.click(screen.getByText('hit.panel.details.exit'));
    expect(mockOnClose).toHaveBeenCalled();

    unmount();
    expect(mockEmit).toHaveBeenCalledWith({ broadcast: false, action: 'stop_viewing', id: 'hit-1' });
  });

  it('loads a missing non-hit record from props and avoids socket activity when closed', async () => {
    parameterContextValue = { selected: undefined };
    recordContextValue = {
      getRecord: mockGetRecord,
      records: {
        'event-1': {
          __index: 'event',
          howler: {
            id: 'event-1'
          }
        }
      }
    };
    socketContextValue = { emit: mockEmit, open: false };
    locationValue = { pathname: '/bundles/test' };

    render(<InformationPane selected="event-1" />);

    await waitFor(() => expect(mockGetRecord).toHaveBeenCalledWith('event-1', true));
    expect(mockEmit).not.toHaveBeenCalled();
    expect(screen.queryByText('plugin-viewing')).not.toBeInTheDocument();
    expect(screen.queryByText('hit-actions')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('details'));
    await waitFor(() => expect(screen.getByText('details:event')).toBeInTheDocument());
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC, PropsWithChildren } from 'react';
import type * as MuiMaterial from '@mui/material';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockEmit = vi.hoisted(() => vi.fn());
const mockExecutePlugin = vi.hoisted(() => vi.fn());
const mockOpen = vi.hoisted(() => ({ current: true }));
const mockParams = vi.hoisted(() => ({ id: 'hit-1' as string | undefined }));
const mockGetHit = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockGetMatchingDossiers = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockGetMatchingOverview = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockNavigate = vi.hoisted(() => vi.fn());
const mockUseMediaQuery = vi.hoisted(() => vi.fn(() => false));
const mockSetOrientation = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', async () => {
  const actual = await vi.importActual<typeof MuiMaterial>('@mui/material');

  return {
    ...actual,
    useMediaQuery: mockUseMediaQuery
  };
});

vi.mock('plugins/store', () => ({
  default: {
    plugins: ['test-plugin']
  }
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecutePlugin })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en' }
  })
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');

  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => mockParams
  };
});

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({
    getMatchingAnalytic: mockGetMatchingAnalytic,
    getMatchingDossiers: mockGetMatchingDossiers,
    getMatchingOverview: mockGetMatchingOverview
  })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: () => [Orientation.VERTICAL, mockSetOrientation]
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: () => []
}));

vi.mock('utils/recordFunctions', () => ({
  getUserList: () => new Set(['analyst'])
}));

vi.mock('utils/utils', () => ({
  tryParse: (value: string) => `parsed:${value}`
}));

vi.mock('components/elements/hit/HitActions', () => ({
  default: ({ orientation }: { orientation: string }) => <div>actions:{orientation}</div>
}));

vi.mock('components/elements/display/icons/SocketBadge', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitBanner', () => ({
  default: () => <div>banner</div>
}));

vi.mock('components/elements/hit/HitOutline', () => ({
  default: () => <div>outline</div>
}));

vi.mock('components/elements/hit/HitLabels', () => ({
  default: () => <div>labels</div>
}));

vi.mock('components/elements/hit/HitLinks', () => ({
  default: ({ analytic, dossiers }: { analytic?: Analytic; dossiers: Dossier[] }) => (
    <div>
      links:{analytic?.analytic_id}:{dossiers.length}
    </div>
  )
}));

vi.mock('components/elements/hit/HitOverview', () => ({
  default: () => <div>overview-content</div>
}));

vi.mock('components/elements/ObjectDetails', () => ({
  default: () => <div>details-content</div>
}));

vi.mock('components/elements/display/json/JSONViewer', () => ({
  default: ({ data }: { data: unknown }) => <div id="json-content">{JSON.stringify(data)}</div>
}));

vi.mock('components/elements/record/RecordComments', () => ({
  default: () => <div>comments-content</div>
}));

vi.mock('components/elements/record/RecordWorklog', () => ({
  default: () => <div>worklog-content</div>
}));

vi.mock('components/elements/record/RecordRelated', () => ({
  default: () => <div>related-content</div>
}));

vi.mock('./LeadRenderer', () => ({
  default: ({ lead }: { lead: { label: { en: string } } }) => <div>lead-content:{lead.label.en}</div>
}));

import HitViewer, { Orientation } from './HitViewer';

const hit: Hit = {
  __index: 'hit',
  timestamp: '2026-01-01T00:00:00Z',
  howler: {
    id: 'hit-1',
    analytic: 'analytic-1',
    assignment: 'analyst',
    hash: 'hash-1',
    data: ['{"source":"data"}'],
    dossier: [
      {
        label: { en: 'Local lead', fr: 'Piste locale' },
        format: 'markdown',
        content: 'local'
      }
    ],
    comment: [{}]
  }
};

const recordContextValue: { records: Record<string, Hit>; getRecord: typeof mockGetHit } = {
  records: { 'hit-1': hit },
  getRecord: mockGetHit
};

const createWrapper = (): FC<PropsWithChildren> => {
  const Wrapper: FC<PropsWithChildren> = ({ children }) => (
    <SocketContext.Provider
      value={
        {
          emit: mockEmit,
          open: mockOpen.current,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          status: 1,
          reconnect: vi.fn(),
          viewers: {},
          fetchViewers: vi.fn()
        } as any
      }
    >
      <RecordContext.Provider value={recordContextValue as any}>{children}</RecordContext.Provider>
    </SocketContext.Provider>
  );

  return Wrapper;
};

const renderViewer = () => render(<HitViewer />, { wrapper: createWrapper() });

beforeEach(() => {
  mockEmit.mockReset();
  mockExecutePlugin.mockReset();
  mockOpen.current = true;
  mockParams.id = 'hit-1';
  mockUseMediaQuery.mockReset().mockReturnValue(false);
  mockSetOrientation.mockReset();
  mockGetHit.mockReset().mockResolvedValue(undefined);
  mockGetMatchingAnalytic.mockReset().mockResolvedValue(undefined);
  mockGetMatchingDossiers.mockReset().mockResolvedValue([]);
  mockGetMatchingOverview.mockReset().mockResolvedValue(undefined);
  mockNavigate.mockReset();
  recordContextValue.records = { 'hit-1': hit };
});

describe('HitViewer', () => {
  it('loads a missing hit and shows the loading state', async () => {
    recordContextValue.records = {};

    renderViewer();

    expect(screen.queryByText('details-content')).not.toBeInTheDocument();
    await waitFor(() => expect(mockGetHit).toHaveBeenCalledWith('hit-1', true));
  });

  it('navigates to the not-found page when loading fails with a 404', async () => {
    recordContextValue.records = {};
    mockGetHit.mockRejectedValue({ cause: { api_status_code: 404 } });

    renderViewer();

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/404'));
  });

  it('fetches matching data, notifies plugins, and renders the details view', async () => {
    const analytic = { analytic_id: 'analytic-1' };
    const dossiers = [{ leads: [] }];
    mockGetMatchingAnalytic.mockResolvedValue(analytic);
    mockGetMatchingDossiers.mockResolvedValue(dossiers);

    renderViewer();

    await waitFor(() => {
      expect(mockGetMatchingAnalytic).toHaveBeenCalledWith(hit);
      expect(mockGetMatchingDossiers).toHaveBeenCalledWith(hit);
      expect(screen.getByText('links:analytic-1:1')).toBeInTheDocument();
    });
    expect(screen.getByText('details-content')).toBeInTheDocument();
    expect(mockExecutePlugin).toHaveBeenCalledWith('test-plugin.on', 'viewing');
  });

  it('emits viewing and stop_viewing socket events', async () => {
    const { unmount } = renderViewer();

    await waitFor(() => {
      expect(mockEmit).toHaveBeenCalledWith({
        broadcast: false,
        action: 'viewing',
        id: 'hit-1'
      });
    });

    mockEmit.mockClear();
    unmount();

    expect(mockEmit).toHaveBeenCalledWith({
      broadcast: false,
      action: 'stop_viewing',
      id: 'hit-1'
    });
  });

  it('does not emit socket events when the socket is closed or no hit id is present', async () => {
    mockOpen.current = false;
    renderViewer();

    await waitFor(() => expect(mockGetMatchingOverview).toHaveBeenCalledWith(hit));
    expect(mockEmit).not.toHaveBeenCalled();

    mockParams.id = undefined;
    renderViewer();

    expect(mockEmit).not.toHaveBeenCalled();
  });

  it('opens an overview by default and lets the analyst select all content tabs', async () => {
    const user = userEvent.setup();
    mockGetMatchingOverview.mockResolvedValue({ content: 'overview' });
    mockGetMatchingDossiers.mockResolvedValue([
      {
        leads: [
          {
            label: { en: 'External lead', fr: 'Piste externe' },
            format: 'markdown',
            content: 'external'
          }
        ]
      }
    ]);

    renderViewer();

    await screen.findByText('overview-content');
    await user.click(screen.getByRole('tab', { name: 'hit.viewer.details' }));
    expect(screen.getByText('details-content')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Local lead' }));
    expect(screen.getByText('lead-content:Local lead')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'External lead' }));
    expect(screen.getByText('lead-content:External lead')).toBeInTheDocument();

    const tabs = screen.getAllByRole('tab');
    await user.click(tabs.at(-5)!);
    expect(screen.getByTestId('json-content')).toHaveTextContent(JSON.stringify(['parsed:{"source":"data"}']));
    await user.click(tabs.at(-4)!);
    expect(screen.getByTestId('json-content')).toHaveTextContent(JSON.stringify(hit));
    await user.click(tabs.at(-3)!);
    expect(screen.getByText('comments-content')).toBeInTheDocument();
    await user.click(tabs.at(-2)!);
    expect(screen.getByText('worklog-content')).toBeInTheDocument();
    await user.click(tabs.at(-1)!);
    expect(screen.getByText('related-content')).toBeInTheDocument();
  });

  it('toggles the desktop layout and navigates to its matching analytic', async () => {
    const user = userEvent.setup();
    mockGetMatchingAnalytic.mockResolvedValue({ analytic_id: 'analytic-1' });

    renderViewer();

    await screen.findByText('links:analytic-1:0');
    const buttons = screen.getAllByRole('button');
    await user.click(buttons[0]);
    expect(mockSetOrientation).toHaveBeenCalledWith(Orientation.HORIZONTAL);

    await user.click(buttons[1]);
    expect(mockNavigate).toHaveBeenCalledWith('/analytics/analytic-1');
  });

  it('forces a horizontal layout below the large breakpoint', async () => {
    mockUseMediaQuery.mockReturnValue(true);

    renderViewer();

    await waitFor(() => expect(mockSetOrientation).toHaveBeenCalledWith(Orientation.HORIZONTAL));
  });
});

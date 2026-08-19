import { render, waitFor } from '@testing-library/react';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { SocketContext } from 'components/app/providers/SocketProvider';
import type { FC, PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockEmit = vi.hoisted(() => vi.fn());
const mockExecutePlugin = vi.hoisted(() => vi.fn());
const mockOpen = vi.hoisted(() => ({ current: true }));
const mockParams = vi.hoisted(() => ({ id: 'hit-1' }));
const mockGetHit = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockGetMatchingDossiers = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockGetMatchingOverview = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockNavigate = vi.hoisted(() => vi.fn());

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
  useMyLocalStorageItem: () => ['vertical', vi.fn()]
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: () => []
}));

vi.mock('utils/recordFunctions', () => ({
  getUserList: () => new Set()
}));

vi.mock('utils/utils', () => ({
  tryParse: (value: unknown) => value
}));

vi.mock('commons/components/pages/PageCenter', () => ({
  default: ({ children }: PropsWithChildren) => <>{children}</>
}));

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children }: PropsWithChildren) => <>{children}</>
}));

vi.mock('components/elements/display/icons/SocketBadge', () => ({
  default: () => null
}));

vi.mock('components/elements/display/json/JSONViewer', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitActions', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitBanner', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitLabels', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitLinks', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitOutline', () => ({
  default: () => null
}));

vi.mock('components/elements/hit/HitOverview', () => ({
  default: () => null
}));

vi.mock('components/elements/ObjectDetails', () => ({
  default: () => null
}));

vi.mock('components/elements/record/RecordComments', () => ({
  default: () => null
}));

vi.mock('components/elements/record/RecordRelated', () => ({
  default: () => null
}));

vi.mock('components/elements/record/RecordWorklog', () => ({
  default: () => null
}));

vi.mock('./LeadRenderer', () => ({
  default: () => null
}));

import HitViewer from './HitViewer';

const recordContextValue = {
  records: {
    'hit-1': {
      howler: {
        data: [],
        dossier: [],
        comment: []
      }
    }
  },
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

beforeEach(() => {
  mockEmit.mockReset();
  mockExecutePlugin.mockReset();
  mockOpen.current = true;
  mockParams.id = 'hit-1';
  mockGetHit.mockClear().mockResolvedValue(undefined);
  mockGetMatchingAnalytic.mockClear().mockResolvedValue(undefined);
  mockGetMatchingDossiers.mockClear().mockResolvedValue([]);
  mockGetMatchingOverview.mockClear().mockResolvedValue(undefined);
  mockNavigate.mockReset();
});

describe('HitViewer', () => {
  it('emits the plugin viewing event', async () => {
    render(<HitViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockGetMatchingOverview).toHaveBeenCalled();
    });

    expect(mockExecutePlugin).toHaveBeenCalledWith('test-plugin.on', 'viewing');
  });

  it('emits viewing and stop_viewing socket events', async () => {
    const { unmount } = render(<HitViewer />, { wrapper: createWrapper() });

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

  it('does not emit socket events when the socket is closed', async () => {
    mockOpen.current = false;

    render(<HitViewer />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockGetMatchingOverview).toHaveBeenCalled();
    });

    expect(mockEmit).not.toHaveBeenCalled();
  });
});

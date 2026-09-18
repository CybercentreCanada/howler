/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const userListContextToken = vi.hoisted(() => ({ name: 'user-list-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSearchUsers = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());

let paramsValue: any = { id: 'an-1' };
let searchParamsValue = new URLSearchParams();
let apiConfigValue: any = { config: { configuration: { features: { notebook: true } } } };
let userListValue: any = {
  users: { owner1: { name: 'Owner Name', email: 'owner@example.com' } },
  searchUsers: mockSearchUsers
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, OpenInNew: () => <div>open-icon</div> };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options, value }: any) => (
    <div>
      <span>{`filter:${value ?? ''}`}</span>
      <button onClick={() => onChange(null, options[0] ?? null)}>change-filter</button>
    </div>
  ),
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children }: any) => <div>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tab: ({ label, onClick, value }: any) => <button data-value={value} onClick={onClick}>{label}</button>,
  Tabs: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, 'comments')}>switch-comments</button>
      {children}
    </div>
  ),
  TextField: ({ label }: any) => <div>{label}</div>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({ spacing: (v: number) => `${v * 8}px` })
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('api', () => ({
  default: {
    analytic: {
      get: (id: string) => ({ op: 'get', id }),
      owner: {
        post: (analyticId: string, body: any) => ({ op: 'owner', analyticId, body })
      }
    }
  }
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/UserListProvider', () => ({
  UserListContext: userListContextToken
}));

vi.mock('components/elements/UserList', () => ({
  default: ({ onChange, userIds }: any) => (
    <button onClick={() => onChange(['owner2'])}>{`user-list:${userIds.join(',')}`}</button>
  )
}));

vi.mock('components/elements/display/HowlerAvatar', () => ({
  default: ({ userId }: any) => <div>{`avatar:${userId}`}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children }: any) => <div>{children}</div>,
  useParams: () => paramsValue,
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('./AnalyticComments', () => ({
  default: () => <div>comments-tab</div>
}));
vi.mock('./AnalyticHitComments', () => ({
  default: () => <div>hit-comments-tab</div>
}));
vi.mock('./AnalyticNotebooks', () => ({
  default: () => <div>notebooks-tab</div>
}));
vi.mock('./AnalyticOverview', () => ({
  default: () => <div>overview-tab</div>
}));
vi.mock('./AnalyticOverviews', () => ({
  default: () => <div>overviews-tab</div>
}));
vi.mock('./AnalyticTemplates', () => ({
  default: () => <div>templates-tab</div>
}));
vi.mock('./TriageSettings', () => ({
  default: () => <div>triage-tab</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return apiConfigValue;
      if (context === userListContextToken) return userListValue;
      return actual.useContext(context);
    }
  };
});

import AnalyticDetails from './AnalyticDetails';

describe('AnalyticDetails', () => {
  beforeEach(() => {
    paramsValue = { id: 'an-1' };
    searchParamsValue = new URLSearchParams();
    apiConfigValue = { config: { configuration: { features: { notebook: true } } } };
    userListValue = {
      users: { owner1: { name: 'Owner Name', email: 'owner@example.com' } },
      searchUsers: mockSearchUsers
    };
    mockDispatchApi.mockReset().mockImplementation(async request => {
      if (request.op === 'owner') {
        return {
          analytic_id: request.analyticId,
          name: 'Analytic Alpha',
          owner: request.body.username,
          contributors: ['owner2', 'user-2'],
          detections: ['det-1', 'det-2']
        };
      }
      return {
        analytic_id: request.id,
        name: 'Analytic Alpha',
        owner: 'owner1',
        contributors: ['owner1', 'user-2'],
        detections: ['det-1', 'det-2']
      };
    });
    mockSearchUsers.mockReset();
    mockSetSearchParams.mockReset();
  });

  it('loads analytics, shows owner and contributors, updates filter params, and changes owner', async () => {
    render(<AnalyticDetails />);

    await waitFor(() => expect(screen.getByText('Analytic Alpha')).toBeInTheDocument());
    expect(screen.getByText('user-list:owner1')).toBeInTheDocument();
    expect(screen.getByText('Owner Name')).toBeInTheDocument();
    expect(screen.getByText('owner@example.com')).toBeInTheDocument();
    expect(screen.getByText('avatar:user-2')).toBeInTheDocument();
    expect(screen.getByText('overview-tab')).toBeInTheDocument();
    expect(mockSearchUsers).toHaveBeenCalledWith('uname:"owner1"');

    fireEvent.click(screen.getByText('switch-comments'));
    await waitFor(() => expect(screen.getByText('comments-tab')).toBeInTheDocument());
    fireEvent.click(screen.getByText('change-filter'));
    await waitFor(() => expect(mockSetSearchParams).toHaveBeenCalled());

    fireEvent.click(screen.getByText('user-list:owner1'));
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { op: 'owner', analyticId: 'an-1', body: { username: 'owner2' } },
        expect.objectContaining({ throwError: true, showError: true })
      )
    );
  });

  it('clears analytic state when no route id exists and hides notebook tabs when disabled', async () => {
    paramsValue = {};
    searchParamsValue = new URLSearchParams('tab=triage');
    apiConfigValue = { config: { configuration: { features: { notebook: false } } } };

    render(<AnalyticDetails />);

    expect(screen.queryByText('route.analytics.tab.notebooks')).not.toBeInTheDocument();
    expect(screen.getAllByText('loading').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText('route.analytics.tab.triage'));
    expect(mockDispatchApi).not.toHaveBeenCalled();
  });
});

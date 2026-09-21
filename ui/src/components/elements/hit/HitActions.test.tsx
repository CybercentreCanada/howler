/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockAssess = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const mockVote = vi.hoisted(() => vi.fn());
const mockSet = vi.hoisted(() => vi.fn());
const mockSetSelected = vi.hoisted(() => vi.fn());
const mockClearSelectedRecords = vi.hoisted(() => vi.fn());
const mockGetCurrentViews = vi.hoisted(() => vi.fn().mockResolvedValue([{ settings: { advance_on_triage: true } }]));
const mockGetMatchingAnalytic = vi.hoisted(() => vi.fn().mockResolvedValue({ triage_settings: { valid_assessments: ['legitimate'], skip_rationale: true } }));
const mockPluginAction = vi.hoisted(() => vi.fn());

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const recordContextToken = vi.hoisted(() => ({ name: 'record-context' }));
const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));

let configValue: any = { lookups: { 'howler.assessment': ['legitimate', 'other'] } };
let localStorageValues: any = { HIT_SHORTCUTS: 'hint', FORCE_DROPDOWN: false };
let showButtonValue = true;

vi.mock('@mui/icons-material', () => ({
  MoreHoriz: () => <div>more-icon</div>
}));

vi.mock('@mui/material', () => ({
  Badge: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  CircularProgress: () => <div>loading</div>,
  Divider: () => <div>divider</div>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  FormControlLabel: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  FormLabel: ({ children }: any) => <div>{children}</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Menu: ({ children, open }: any) => open ? <div>{children}</div> : null,
  Radio: () => <div>radio</div>,
  RadioGroup: ({ children, onChange }: any) => <div><button onClick={() => onChange?.(null, 'shortcut')}>set-shortcuts</button>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Switch: ({ checked, onChange }: any) => <button onClick={() => onChange?.(null, !checked)}>{checked ? 'dropdown-on' : 'dropdown-off'}</button>,
  styled: (_component: any) => (styles: any) => {
    void styles;
    return ({ children }: any) => <div>{children}</div>;
  },
  useMediaQuery: () => showButtonValue
}));

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingAnalytic: mockGetMatchingAnalytic })
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: recordContextToken
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('components/hooks/useHitActions', () => ({
  default: () => ({
    availableTransitions: [{ type: 'action', name: 'Transition', actionFunction: vi.fn(), key: 'T' }],
    canVote: true,
    canAssess: true,
    loading: false,
    assess: mockAssess,
    vote: mockVote,
    selectedVote: 'benign'
  })
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageProvider: () => ({ values: localStorageValues, set: mockSet })
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['plugin-a'] }
}));

vi.mock('react-device-detect', () => ({
  isMobile: false
}));

vi.mock('react-i18next', () => ({
  Trans: ({ i18nKey }: any) => <>{i18nKey}</>
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: () => [{ type: 'action', name: 'PluginAction', actionFunction: mockPluginAction, key: 'P' }] })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => {
    if (context === viewContextToken) return selector({ getCurrentViews: mockGetCurrentViews });
    if (context === parameterContextToken) return selector({ selected: 'hit-1', setSelected: mockSetSelected });
    if (context === recordContextToken) return selector({ clearSelectedRecords: mockClearSelectedRecords });
    if (context === recordSearchContextToken) {
      return selector({
        response: { items: [{ howler: { id: 'hit-1' } }, { howler: { id: 'hit-2' } }] }
      });
    }
    return undefined;
  }
}));

vi.mock('utils/Throttler', () => ({
  default: class {
    debounce(fn: () => void) {
      fn();
    }
  }
}));

vi.mock('utils/constants', () => ({
  StorageKey: {
    HIT_SHORTCUTS: 'HIT_SHORTCUTS',
    FORCE_DROPDOWN: 'FORCE_DROPDOWN'
  }
}));

vi.mock('./actions/ButtonActions', () => ({
  default: ({ actions }: any) => (
    <div>
      {actions.map((action: any) => (
        <button key={action.name} onClick={action.actionFunction}>{action.name}</button>
      ))}
    </div>
  )
}));

vi.mock('./actions/DropdownActions', () => ({
  default: ({ actions }: any) => <div>{`dropdown:${actions.length}`}</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      return actual.useContext(context);
    }
  };
});

import HitActions from './HitActions';

describe('HitActions', () => {
  it('builds desktop actions, supports keyboard shortcuts, advances after assessment, and saves settings', async () => {
    localStorageValues = { HIT_SHORTCUTS: 'hint', FORCE_DROPDOWN: false };
    showButtonValue = true;
    render(<HitActions hit={{ howler: { id: 'hit-1', status: 'open', assessment: '' } } as any} />);

    await waitFor(() => expect(mockGetMatchingAnalytic).toHaveBeenCalled());
    expect(screen.getByText('Transition')).toBeInTheDocument();
    expect(screen.getByText('PluginAction')).toBeInTheDocument();
    expect(screen.getByText('legitimate')).toBeInTheDocument();
    expect(screen.getByText('Benign')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'P' });
    expect(mockPluginAction).toHaveBeenCalled();

    fireEvent.click(screen.getByText('legitimate'));
    await waitFor(() => expect(mockAssess).toHaveBeenCalledWith('legitimate', true));
    expect(mockClearSelectedRecords).toHaveBeenCalledWith('hit-2');
    expect(mockSetSelected).toHaveBeenCalledWith('hit-2');

    fireEvent.click(screen.getByText('more-icon'));
    fireEvent.click(screen.getByText('set-shortcuts'));
    fireEvent.click(screen.getByText('dropdown-off'));

    expect(mockSet).toHaveBeenCalledWith('HIT_SHORTCUTS', 'shortcut');
    expect(mockSet).toHaveBeenCalledWith('FORCE_DROPDOWN', true);
  });

  it('renders dropdown actions when forced', async () => {
    localStorageValues = { HIT_SHORTCUTS: 'no', FORCE_DROPDOWN: true };
    showButtonValue = false;

    render(<HitActions hit={{ howler: { id: 'hit-1', status: 'open', assessment: '' } } as any} orientation="vertical" />);

    await waitFor(() => expect(screen.getByText('dropdown:6')).toBeInTheDocument());
  });
});

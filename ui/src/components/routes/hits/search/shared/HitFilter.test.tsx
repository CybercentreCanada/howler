/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockSetSavedFilter = vi.hoisted(() => vi.fn());
const mockRemoveSavedFilter = vi.hoisted(() => vi.fn());

let configValue: any = { lookups: { 'howler.assessment': ['malicious'] } };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, FilterList: () => <div>filter-icon</div> };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options, disabled }: any) => (
    <button disabled={disabled} onClick={() => onChange(null, options.includes('event.provider') ? 'event.provider' : options[0])}>change-filter</button>
  ),
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>,
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

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children, label, onDelete }: any) => <div><div>{label}</div><button onClick={onDelete}>delete-filter</button>{children}</div>
}));

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({ dispatchApi: mockDispatchApi })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) =>
    selector({ setFilter: mockSetSavedFilter, removeFilter: mockRemoveSavedFilter })
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

import HitFilter from './HitFilter';

describe('HitFilter', () => {
  beforeEach(() => {
    configValue = { lookups: { 'howler.assessment': ['malicious'] } };
    mockDispatchApi.mockReset().mockImplementation(async value => ({ 'event.provider': { azure: 2 } }));
    mockSetSavedFilter.mockReset();
    mockRemoveSavedFilter.mockReset();
  });

  it('initializes from value, fetches custom lookups, updates values, and removes filters', async () => {
    render(<HitFilter id={1} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(1, 'howler.assessment:*'));

    fireEvent.click(screen.getAllByText('change-filter')[0]);
    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith(
        { query: 'howler.id:*', fields: ['event.provider'], rows: 100 },
        { throwError: false }
      )
    );

    fireEvent.click(screen.getAllByText('change-filter')[1]);
    expect(mockSetSavedFilter).toHaveBeenCalledWith(1, 'event.provider:"azure"');

    fireEvent.click(screen.getByText('delete-filter'));
    expect(mockRemoveSavedFilter).toHaveBeenCalledWith('howler.assessment:*');
  });

  it('uses configured lookups and wildcard values', async () => {
    render(<HitFilter id={2} value={'howler.assessment:*'} />);
    await waitFor(() => expect(mockSetSavedFilter).toHaveBeenCalledWith(2, 'howler.assessment:*'));
  });
});

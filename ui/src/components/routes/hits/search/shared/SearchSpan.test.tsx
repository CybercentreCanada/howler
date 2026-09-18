/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));

const mockSetSpan = vi.hoisted(() => vi.fn());
const mockGetCurrentViews = vi.hoisted(() => vi.fn());

let locationValue = { search: '' };
let parameterValue: any = {
  views: [],
  span: 'date.range.1.day',
  setSpan: mockSetSpan,
  startDate: undefined,
  endDate: undefined
};

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, AvTimer: () => <div>timer-icon</div> };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options }: any) => <button onClick={() => onChange(null, options.at(-1))}>change-span</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ label }: any) => <div>{label}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ParameterProvider', () => ({
  ParameterContext: parameterContextToken
}));

vi.mock('components/app/providers/ViewProvider', () => ({
  ViewContext: viewContextToken
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children, label }: any) => <div><div>{label}</div>{children}</div>
}));

vi.mock('dayjs', () => ({
  default: () => ({ subtract: () => ({ format: () => '2024-01-01 00:00' }) })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) => selector(context === parameterContextToken ? parameterValue : { getCurrentViews: mockGetCurrentViews })
}));

vi.mock('utils/utils', () => ({
  convertLuceneToDate: (value: string) => `converted:${value}`
}));

vi.mock('./CustomSpan', () => ({
  default: () => <div>custom-span</div>
}));

import SearchSpan from './SearchSpan';

describe('SearchSpan', () => {
  beforeEach(() => {
    locationValue = { search: '' };
    parameterValue = {
      views: [],
      span: 'date.range.1.day',
      setSpan: mockSetSpan,
      startDate: undefined,
      endDate: undefined
    };
    mockSetSpan.mockReset();
    mockGetCurrentViews.mockReset();
  });

  it('loads the span from the current view and handles custom selection', async () => {
    mockGetCurrentViews.mockResolvedValueOnce([{ span: 'date.range.1.week' }]);
    render(<SearchSpan />);
    await waitFor(() => expect(mockSetSpan).toHaveBeenCalledWith('date.range.1.week'));

    fireEvent.click(screen.getByText('change-span'));
    expect(mockSetSpan).toHaveBeenCalledWith('date.range.custom');
    expect(screen.getByText('custom-span')).toBeInTheDocument();
  });

  it('converts lucene date spans and skips view lookup when span is already in the URL', async () => {
    mockGetCurrentViews.mockResolvedValueOnce([{ span: '2024-01-01T00:00:00Z:2024-01-02T00:00:00Z' }]);
    render(<SearchSpan />);
    await waitFor(() =>
      expect(mockSetSpan).toHaveBeenCalledWith('converted:2024-01-01T00:00:00Z:2024-01-02T00:00:00Z')
    );

    locationValue = { search: '?span=date.range.1.month' };
    render(<SearchSpan omitCustom />);
    expect(mockGetCurrentViews).toHaveBeenCalledTimes(1);
  });
});

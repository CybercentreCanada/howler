/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const parameterContextToken = vi.hoisted(() => ({ name: 'parameter-context' }));
const viewContextToken = vi.hoisted(() => ({ name: 'view-context' }));
const mockSetSavedSort = vi.hoisted(() => vi.fn());
const mockGetCurrentViews = vi.hoisted(() => vi.fn());

let locationValue = { search: '' };
let parameterValue: any = { views: [], sort: 'event.created desc', setSort: mockSetSavedSort };

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, Sort: () => <div>sort-icon</div> };
});

vi.mock('@mui/material', () => ({
  Autocomplete: ({ onChange, options }: any) => <button onClick={() => onChange(null, options.at(-1))}>change-sort</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: () => <div>text-field</div>
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

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  useLocation: () => locationValue
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (context: any, selector: any) =>
    selector(context === parameterContextToken ? parameterValue : { getCurrentViews: mockGetCurrentViews })
}));

vi.mock('./CustomSort', () => ({
  default: () => <div>custom-sort</div>
}));

import HitSort from './HitSort';

describe('HitSort', () => {
  beforeEach(() => {
    locationValue = { search: '' };
    parameterValue = { views: [], sort: 'event.created desc', setSort: mockSetSavedSort };
    mockSetSavedSort.mockReset();
    mockGetCurrentViews.mockReset();
  });

  it('loads the current view sort and switches to custom sorting when requested', async () => {
    mockGetCurrentViews.mockResolvedValueOnce([{ sort: 'howler.score asc' }]);
    render(<HitSort />);
    await waitFor(() => expect(mockSetSavedSort).toHaveBeenCalledWith('howler.score asc'));

    fireEvent.click(screen.getAllByText('change-sort')[0]!);
    expect(screen.getByText('custom-sort')).toBeInTheDocument();
  });

  it('skips view lookup when sort is in the URL', () => {
    locationValue = { search: '?sort=event.created%20asc' };
    render(<HitSort />);
    expect(mockGetCurrentViews).not.toHaveBeenCalled();
  });
});

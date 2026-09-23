/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());
const setters = vi.hoisted(() => Array.from({ length: 9 }, () => vi.fn()));

const storageValues = [true, false, false, true, 'normal', 'list', 25, null, null];

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    List: () => <div>list-icon</div>,
    TableChart: () => <div>table-icon</div>,
    ViewComfy: () => <div>comfy-icon</div>,
    ViewCompact: () => <div>dense-icon</div>,
    ViewModule: () => <div>normal-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  MenuItem: ({ children }: any) => <option>{children}</option>,
  Select: ({ value, onChange }: any) => (
    <select aria-label="page-count" value={value} onChange={onChange}>
      <option value={5}>5</option>
      <option value={25}>25</option>
      <option value={50}>50</option>
    </select>
  ),
  Stack: ({ children }: any) => <div>{children}</div>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children }: any) => <div>{children}</div>,
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, 'dense')}>choose-layout</button>
      <button onClick={() => onChange(null, 'grid')}>choose-display</button>
      {children}
    </div>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: vi.fn((_: string, defaultValue: any) => {
    const index = (vi.mocked as any).calls ?? 0;
    return [storageValues[index] ?? defaultValue, setters[index]];
  })
}));

vi.mock('plugins/store', () => ({
  default: { plugins: ['demo'] }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('../../elements/EditRow', () => ({
  default: ({ titleKey, onEdit, value }: any) => (
    <button onClick={() => onEdit?.('true')}>{`${titleKey}:${String(value)}`}</button>
  )
}));

vi.mock('./SettingsSection', () => ({
  default: ({ children, title }: any) => <div><span>{title}</span>{children}</div>
}));

import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import LocalSection from './LocalSection';

describe('LocalSection', () => {
  beforeEach(() => {
    let call = 0;
    vi.mocked(useMyLocalStorageItem).mockImplementation((_: string, defaultValue: any) => {
      const index = call++;
      return [storageValues[index] ?? defaultValue, setters[index]] as any;
    });
    setters.forEach(fn => fn.mockReset());
    mockExecuteFunction.mockReset();
    mockExecuteFunction.mockReturnValue(<div>local-plugin</div>);
  });

  it('updates stored local preferences and renders plugin settings', () => {
    render(<LocalSection />);

    fireEvent.click(screen.getByText('page.settings.local.compact.json:true'));
    expect(setters[0]).toHaveBeenCalledWith(true);

    fireEvent.click(screen.getAllByText('choose-layout')[0]);
    expect(setters[4]).toHaveBeenCalledWith('dense');

    fireEvent.click(screen.getAllByText('choose-display')[1]);
    expect(setters[5]).toHaveBeenCalledWith('grid');

    fireEvent.change(screen.getByLabelText('page-count'), { target: { value: '50' } });
    expect(setters[6]).toHaveBeenCalledWith(50);
    expect(screen.getByText('local-plugin')).toBeInTheDocument();
  });
});

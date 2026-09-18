/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const recordSearchContextToken = vi.hoisted(() => ({ name: 'record-search' }));
const mockSetDisplayType = vi.hoisted(() => vi.fn());
const mockSetHitLayout = vi.hoisted(() => vi.fn());
const mockSetTemplateFieldCount = vi.hoisted(() => vi.fn());

let localStorageValues: Record<string, any> = {};
let storageCall = 0;

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    ArrowDropDown: () => <div>arrow-icon</div>,
    InfoOutlined: () => <div>info-icon</div>,
    Settings: () => <div>settings-icon</div>,
    ViewComfy: () => <div>comfy-icon</div>,
    ViewCompact: () => <div>compact-icon</div>,
    ViewModule: () => <div>normal-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Checkbox: ({ checked, onChange }: any) => <input aria-label="field-toggle" type="checkbox" checked={checked} onChange={e => onChange(null, e.target.checked)} />,
  Divider: () => <div>divider</div>,
  FormLabel: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ value, onChange, disabled }: any) => <input aria-label="field-count" disabled={disabled} value={value} onChange={onChange} />,
  ToggleButton: ({ children, value }: any) => <button data-value={value}>{children}</button>,
  ToggleButtonGroup: ({ onChange, children }: any) => <div><button onClick={() => onChange(null, 'dense')}>set-layout</button>{children}</div>,
  Tooltip: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/RecordSearchProvider', () => ({
  RecordSearchContext: recordSearchContextToken
}));

vi.mock('components/elements/display/ChipPopper', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/hit/HitLayout', () => ({
  HitLayout: { DENSE: 'dense', NORMAL: 'normal', COMFY: 'comfy' }
}));

vi.mock('components/elements/view/LayoutToggle', () => ({
  __esModule: true,
  default: ({ setDisplayType }: any) => <button onClick={() => setDisplayType('grid')}>layout-toggle</button>
}));

vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: (key: string) => {
    storageCall += 1;
    if (storageCall % 2 === 1) return [localStorageValues.hitLayout, mockSetHitLayout];
    return [localStorageValues.templateFieldCount, mockSetTemplateFieldCount];
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: (_context: any, selector: any) => selector({ displayType: 'list', setDisplayType: mockSetDisplayType })
}));

import LayoutSettings from './LayoutSettings';

describe('LayoutSettings', () => {
  beforeEach(() => {
    localStorageValues = { hitLayout: 'normal', templateFieldCount: null };
    storageCall = 0;
    mockSetDisplayType.mockReset();
    mockSetHitLayout.mockReset();
    mockSetTemplateFieldCount.mockReset();
  });

  it('updates display type, layout, and template field count settings', () => {
    const { unmount } = render(<LayoutSettings />);

    fireEvent.click(screen.getByText('layout-toggle'));
    expect(mockSetDisplayType).toHaveBeenCalledWith('grid');

    fireEvent.click(screen.getByText('set-layout'));
    expect(mockSetHitLayout).toHaveBeenCalledWith('dense');

    fireEvent.click(screen.getByLabelText('field-toggle'));
    expect(mockSetTemplateFieldCount).toHaveBeenCalledWith(3);

    localStorageValues.templateFieldCount = 3;
    storageCall = 0;
    unmount();
    render(<LayoutSettings />);
    fireEvent.change(screen.getByLabelText('field-count'), { target: { value: '20' } });
    expect(mockSetTemplateFieldCount).toHaveBeenCalledWith(15);
  });
});

/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockExecuteFunction = vi.hoisted(() => vi.fn());
const mockSetSearchParams = vi.hoisted(() => vi.fn());

let searchParamsValue = new URLSearchParams();
let pluginList = ['demo'];

vi.mock('@mui/material', () => ({
  Stack: ({ children }: any) => <div>{children}</div>,
  Tab: ({ label, value }: any) => <button data-value={value}>{label}</button>,
  Tabs: ({ children, onChange }: any) => (
    <div>
      <button onClick={() => onChange(null, 'second')}>switch-tab</button>
      {children}
    </div>
  )
}));

vi.mock('@tui/core', () => ({
  PageCenter: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: any) => <div>{md}</div>
}));

vi.mock('plugins/store', () => ({
  default: {
    get plugins() {
      return pluginList;
    }
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } })
}));

vi.mock('react-pluggable', () => ({
  usePluginStore: () => ({ executeFunction: mockExecuteFunction })
}));

vi.mock('react-router', () => ({
  useSearchParams: () => [searchParamsValue, mockSetSearchParams]
}));

vi.mock('./markdown/integrations.en.md', () => ({ default: 'integrations-en' }));
vi.mock('./markdown/integrations.fr.md', () => ({ default: 'integrations-fr' }));

import Integrations from './Integrations';

describe('Integrations', () => {
  beforeEach(() => {
    searchParamsValue = new URLSearchParams();
    pluginList = ['demo'];
    mockExecuteFunction.mockReset();
    mockSetSearchParams.mockReset();
  });

  it('renders plugin integrations and syncs the selected tab into search params', () => {
    mockExecuteFunction.mockReturnValue([
      ['first', () => <div>first-view</div>],
      ['second', () => <div>second-view</div>]
    ]);
    render(<Integrations />);

    expect(screen.getByText('route.integrations.first')).toBeInTheDocument();
    expect(screen.getByText('first-view')).toBeInTheDocument();
    fireEvent.click(screen.getByText('switch-tab'));
    expect(mockSetSearchParams).toHaveBeenCalled();
  });

  it('falls back to markdown when no plugin integrations exist', () => {
    pluginList = [];
    render(<Integrations />);
    expect(screen.getByText('integrations-en')).toBeInTheDocument();
  });
});

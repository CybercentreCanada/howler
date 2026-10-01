/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/icons-material', () => ({
  ArrowDropDown: () => <div>expand-icon</div>,
  InfoOutlined: () => <div>info-icon</div>
}));

vi.mock('@mui/material', () => ({
  Accordion: ({ children }: any) => <div>{children}</div>,
  AccordionDetails: ({ children }: any) => <div>{children}</div>,
  AccordionSummary: ({ children }: any) => <div>{children}</div>,
  Box: ({ children }: any) => <div>{children}</div>,
  Divider: () => <div>divider</div>,
  Grid: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  TextField: ({ value, onChange, label }: any) => (
    <label>
      {label}
      <input aria-label={label} value={value} onChange={onChange} />
    </label>
  ),
  Tooltip: ({ children }: any) => <>{children}</>,
  Typography: ({ children }: any) => <div>{children}</div>,
  useTheme: () => ({
    palette: { divider: '#ddd' },
    spacing: (n: number) => `${n * 8}px`
  })
}));

vi.mock('components/elements/PluginTypography', () => ({
  default: ({ children }: any) => <span>{children}</span>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/Throttler', () => ({
  default: class {
    debounce(fn: () => void) {
      fn();
    }
  }
}));

import ObjectDetails from './ObjectDetails';

describe('ObjectDetails', () => {
  it('renders grouped sections, nested values, and filters by search query', async () => {
    render(
      <ObjectDetails
        obj={
          {
            event: {
              id: 'evt-1',
              nested: { key: 'value' },
              dup: ['alpha', 'alpha', 'beta']
            },
            source: {
              ip: '1.1.1.1',
              port: 443,
              enabled: false
            },
            howler: { id: 'skip-me' },
            labels: { tag: 'skip' },
            __hidden: { value: 'skip' }
          } as any
        }
      />
    );

    expect(screen.getByText('Event')).toBeInTheDocument();
    expect(screen.getByText('Source')).toBeInTheDocument();
    expect(screen.queryByText('Howler')).not.toBeInTheDocument();
    expect(screen.getByText('evt-1')).toBeInTheDocument();
    expect(screen.getByText('value')).toBeInTheDocument();
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('beta')).toBeInTheDocument();
    expect(screen.getByText('info-icon')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('overview.search'), { target: { value: 'ip' } });

    await waitFor(() => {
      expect(screen.getByText('1.1.1.1')).toBeInTheDocument();
      expect(screen.queryByText('evt-1')).not.toBeInTheDocument();
    });
  });
});

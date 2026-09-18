/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockStacked = vi.hoisted(() => vi.fn(({ field }: any) => <div>{field}</div>));

vi.mock('@mui/material', () => ({
  useTheme: () => ({ palette: { grey: { 500: '#999' } } })
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('./Stacked', () => ({
  default: (props: any) => mockStacked(props)
}));

import Detection from './Detection';
import Status from './Status';

describe('Detection and Status', () => {
  it('pass their analytic fields into the shared stacked widget', () => {
    render(
      <div>
        <Detection analytic={{ name: 'Alpha' } as any} />
        <Status analytic={{ name: 'Alpha' } as any} />
      </div>
    );

    expect(screen.getByText('howler.detection')).toBeInTheDocument();
    expect(screen.getByText('howler.status')).toBeInTheDocument();
  });
});

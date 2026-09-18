/// <reference types="vitest" />
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockRegister = vi.hoisted(() => vi.fn());

vi.mock('@mui/material', () => ({
  useTheme: () => ({
    palette: {
      text: { primary: '#111111', secondary: '#999999' }
    }
  })
}));

vi.mock('chart.js', () => {
  const token = {};
  return {
    ArcElement: token,
    BarElement: token,
    CategoryScale: token,
    Filler: token,
    Legend: token,
    LinearScale: token,
    LineElement: token,
    PointElement: token,
    SubTitle: token,
    TimeScale: token,
    Title: token,
    Tooltip: token,
    Chart: {
      defaults: { font: {} as any },
      register: mockRegister
    }
  };
});

vi.mock('chartjs-plugin-zoom', () => ({
  default: { id: 'zoom' }
}));

vi.mock('chartjs-adapter-dayjs-4', () => ({}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => `translated:${key}` })
}));

import useMyChart from './useMyChart';

describe('useMyChart', () => {
  it('registers chart primitives and builds line options', () => {
    const { result } = renderHook(() => useMyChart());
    const line = result.current.line('title.key', 'subtitle.key');

    expect(mockRegister).toHaveBeenCalled();
    expect(line.plugins.title.text).toBe('translated:title.key');
    expect(line.plugins.zoom.pan.mode).toBe('x');
    expect(line.plugins.subtitle).toBeUndefined();
    expect(line.scales.x.type).toBe('time');
  });

  it('builds doughnut, bar, and scatter options', () => {
    const { result } = renderHook(() => useMyChart());
    const doughnut = result.current.doughnut('doughnut.title');
    const bar = result.current.bar('bar.title');
    const scatter = result.current.scatter('scatter.title', 'scatter.subtitle');

    expect(doughnut.scales).toBeUndefined();
    expect(doughnut.plugins.subtitle.text).toBe('translated:route.analytics.overview.limit');
    expect(bar.plugins.legend).toEqual({ display: false });
    expect(bar.scales.y.ticks).toEqual({ precision: 0, color: '#111111' });
    expect(scatter.plugins.subtitle.text).toBe('translated:scatter.subtitle');
  });
});

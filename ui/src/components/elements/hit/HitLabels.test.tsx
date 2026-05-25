import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import HitLabels from './HitLabels';

/**
 * HitLabels.test.tsx
 *
 * Purpose:
 * This test suite validates the core behavior of the HitLabels component.
 * - Correct transformation of hit.howler.labels into UI chips
 * - Proper rendering of all label values
 * - Conditional display of the edit button based on readOnly mode
 * - Safe rendering when no labels are present
 */

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({
    dispatchApi: vi.fn()
  })
}));

vi.mock('components/app/providers/HitProvider', () => ({
  HitContext: {}
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: () => vi.fn()
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  }),
  Trans: ({ i18nKey }: any) => i18nKey
}));

vi.mock('utils/constants', () => ({
  LABEL_TYPES: {
    security: { icon: null, color: '#ff0000' },
    system: { icon: null, color: '#00ff00' }
  }
}));

const baseHit = {
  howler: {
    id: 'hit-1',
    labels: {
      security: ['critical', 'high'],
      system: ['info']
    }
  }
} as any;

describe('HitLabels', () => {
  it('renders all labels from hit.howler.labels', () => {
    render(<HitLabels hit={baseHit} readOnly={true} />);

    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('info')).toBeInTheDocument();
  });

  it('renders correct number of labels', () => {
    render(<HitLabels hit={baseHit} readOnly={true} />);

    const labels = screen.getAllByText(/critical|high|info/);
    expect(labels.length).toBe(3);
  });

  it('shows edit button when not readOnly', () => {
    render(<HitLabels hit={baseHit} readOnly={false} />);

    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('hides edit button when readOnly', () => {
    render(<HitLabels hit={baseHit} readOnly={true} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders without crashing when labels are empty', () => {
    const emptyHit = {
      howler: {
        id: 'hit-1',
        labels: {}
      }
    } as any;

    const { container } = render(<HitLabels hit={emptyHit} readOnly={true} />);

    expect(container).toBeInTheDocument();
  });
});

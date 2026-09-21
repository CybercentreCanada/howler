import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

const mockDispatchApi = vi.hoisted(() => vi.fn());
const mockUpdateRecord = vi.hoisted(() => vi.fn());

vi.mock('components/hooks/useMyApi', () => ({
  default: () => ({
    dispatchApi: mockDispatchApi
  })
}));

vi.mock('components/app/providers/RecordProvider', () => ({
  RecordContext: {}
}));

vi.mock('use-context-selector', () => ({
  useContextSelector: () => mockUpdateRecord
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  }),
  Trans: ({ i18nKey }: any) => i18nKey
}));

vi.mock('utils/constants', () => ({
  LABEL_TYPES: {
    generic: { icon: null, color: '#0000ff' },
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

  it('opens the drawer, validates empty input, and adds labels', async () => {
    mockDispatchApi.mockResolvedValueOnce({ howler: { labels: { security: ['critical', 'high'], system: ['info'], generic: ['fresh'] } } });

    render(<HitLabels hit={baseHit} readOnly={false} />);

    fireEvent.click(screen.getByRole('button'));
    fireEvent.keyDown(screen.getByLabelText('hit.label.edit.add.label'), { key: 'Enter' });
    expect(screen.getByText('hit.label.edit.add.error.empty')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('hit.label.edit.add.label'), { target: { value: 'fresh' } });
    fireEvent.keyDown(screen.getByLabelText('hit.label.edit.add.label'), { key: 'Enter' });

    await waitFor(() =>
      expect(mockDispatchApi).toHaveBeenCalledWith({ op: 'put', id: 'hit-1', category: 'generic', body: { value: ['fresh'] } })
    );
    expect(mockUpdateRecord).toHaveBeenCalled();
  });
});
vi.mock('api', () => ({
  default: {
    hit: {
      labels: {
        put: (id: string, category: string, body: any) => ({ op: 'put', id, category, body }),
        del: (id: string, category: string, body: any) => ({ op: 'del', id, category, body })
      }
    }
  }
}));

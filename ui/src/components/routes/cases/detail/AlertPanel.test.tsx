import { fireEvent, render, screen } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import { MemoryRouter } from 'react-router';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockHitCardProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('components/elements/hit/HitCard', () => ({
  default: (props: Record<string, unknown>) => {
    mockHitCardProps.current.push(props);
    return <div id={`hit-card-${String(props.id)}`} />;
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key
  })
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    Link: ({ to, children, ...props }: any) => (
      <a href={to} {...props}>
        {children}
      </a>
    )
  };
});

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import AlertPanel from './AlertPanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderPanel = (caseValue: Case | null) => {
  return render(
    <MemoryRouter>
      <AlertPanel case={caseValue as Case} />
    </MemoryRouter>
  );
};

const makeHitItem = (value: string, id = value) => ({
  type: 'hit' as const,
  value,
  id,
  name: null as string | null,
  parent: null as string | null
});

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockHitCardProps.current = [];
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AlertPanel', () => {
  it('renders a skeleton when the case is null', () => {
    const { container } = renderPanel(null);

    expect(container.querySelector('.MuiSkeleton-root')).toBeTruthy();
  });

  it('renders the translated heading key', () => {
    const _case = createMockCase({ case_id: 'case-1', items: [] });

    renderPanel(_case);

    expect(screen.getByText('page.cases.dashboard.alerts')).toBeInTheDocument();
  });

  it('renders HitCard only for unique hit items on the current page', () => {
    const duplicate = makeHitItem('hit-1', '/cases/test/path-a');
    const _case = createMockCase({
      case_id: 'case-2',
      items: [duplicate, duplicate, makeHitItem('hit-2', '/cases/test/path-b'), { type: 'event', value: 'event-1' }]
    });

    renderPanel(_case);

    expect(screen.getByTestId('hit-card-hit-1')).toBeInTheDocument();
    expect(screen.getByTestId('hit-card-hit-2')).toBeInTheDocument();
    expect(screen.queryByTestId('hit-card-event-1')).not.toBeInTheDocument();
    expect(mockHitCardProps.current).toHaveLength(2);

    expect(mockHitCardProps.current[0]).toEqual(
      expect.objectContaining({
        id: 'hit-1',
        lazy: true,
        layout: 'dense'
      })
    );
  });

  it('renders overlay links that target each hit path', () => {
    const _case = createMockCase({
      case_id: 'case-3',
      items: [makeHitItem('hit-1', '/cases/case-3/path-one'), makeHitItem('hit-2', '/cases/case-3/path-two')]
    });

    const { container } = renderPanel(_case);
    const links = Array.from(container.querySelectorAll('a'));

    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', '/cases/case-3/hit-1');
    expect(links[1]).toHaveAttribute('href', '/cases/case-3/hit-2');
  });

  it('shows pagination with multiple pages and switches to page 2 items', () => {
    const items = Array.from({ length: 6 }, (_, idx) => makeHitItem(`hit-${idx + 1}`, `/cases/test/hit-${idx + 1}`));
    const _case = createMockCase({ case_id: 'case-4', items });

    renderPanel(_case);

    expect(screen.getByTestId('hit-card-hit-1')).toBeInTheDocument();
    expect(screen.getByTestId('hit-card-hit-5')).toBeInTheDocument();
    expect(screen.queryByTestId('hit-card-hit-6')).not.toBeInTheDocument();

    const pageTwoButton = screen.getByRole('button', { name: 'Go to page 2' });
    fireEvent.click(pageTwoButton);

    expect(screen.getByTestId('hit-card-hit-6')).toBeInTheDocument();
    expect(screen.queryByTestId('hit-card-hit-1')).not.toBeInTheDocument();
  });
});

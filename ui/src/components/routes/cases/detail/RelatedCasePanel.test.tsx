import { fireEvent, render, screen } from '@testing-library/react';
import type { Case } from 'models/entities/generated/Case';
import { MemoryRouter } from 'react-router';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const mockCaseCardProps = vi.hoisted(() => ({ current: [] as Array<Record<string, unknown>> }));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

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

vi.mock('../../../elements/case/CaseCard', () => ({
  default: (props: Record<string, unknown>) => {
    mockCaseCardProps.current.push(props);
    return <div id={`case-card-${String(props.caseId)}`} />;
  }
}));

// ---------------------------------------------------------------------------
// Imports after mocks
// ---------------------------------------------------------------------------

import RelatedCasePanel from './RelatedCasePanel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const renderPanel = (caseValue: Case | null) => {
  return render(
    <MemoryRouter>
      <RelatedCasePanel case={caseValue as Case} />
    </MemoryRouter>
  );
};

const makeCaseItem = (value: string, id = value) => ({
  type: 'case' as const,
  value,
  id,
  name: null as string | null,
  parent: null as string | null
});

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockCaseCardProps.current = [];
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RelatedCasePanel', () => {
  it('renders a skeleton when the case is null', () => {
    const { container } = renderPanel(null);

    expect(container.querySelector('.MuiSkeleton-root')).toBeTruthy();
  });

  it('renders nothing when the case has no case-type items', () => {
    const baseCase = createMockCase({ case_id: 'case-no-cases', items: [{ type: 'hit', value: 'hit-1' }] as any });
    const { container } = renderPanel(baseCase);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders the translated heading key', () => {
    const _case = createMockCase({ case_id: 'case-1', items: [makeCaseItem('child-1')] });
    renderPanel(_case);

    expect(screen.getByText('page.cases.dashboard.cases')).toBeInTheDocument();
  });

  it('renders CaseCard only for unique case items on the current page', () => {
    const duplicate = makeCaseItem('child-1', '/cases/test/path-a');
    const _case = createMockCase({
      case_id: 'case-2',
      items: [
        duplicate,
        duplicate,
        makeCaseItem('child-2', '/cases/test/path-b'),
        { type: 'event', value: 'event-1' } as any
      ]
    });

    renderPanel(_case);

    expect(screen.getByTestId('case-card-child-1')).toBeInTheDocument();
    expect(screen.getByTestId('case-card-child-2')).toBeInTheDocument();
    expect(screen.queryByTestId('case-card-event-1')).not.toBeInTheDocument();
    expect(mockCaseCardProps.current).toHaveLength(2);

    expect(mockCaseCardProps.current[0]).toEqual(
      expect.objectContaining({
        caseId: 'child-1'
      })
    );
  });

  it('renders overlay links that target each case path', () => {
    const _case = createMockCase({
      case_id: 'case-3',
      items: [makeCaseItem('child-1', '/cases/case-3/path-one'), makeCaseItem('child-2', '/cases/case-3/path-two')]
    });

    const { container } = renderPanel(_case);
    const links = Array.from(container.querySelectorAll('a'));

    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', '/cases/child-1');
    expect(links[1]).toHaveAttribute('href', '/cases/child-2');
  });

  it('shows pagination with multiple pages and switches to page 2 items', () => {
    const items = Array.from({ length: 6 }, (_, idx) =>
      makeCaseItem(`child-${idx + 1}`, `/cases/test/child-${idx + 1}`)
    );
    const _case = createMockCase({ case_id: 'case-4', items });

    renderPanel(_case);

    expect(screen.getByTestId('case-card-child-1')).toBeInTheDocument();
    expect(screen.getByTestId('case-card-child-5')).toBeInTheDocument();
    expect(screen.queryByTestId('case-card-child-6')).not.toBeInTheDocument();

    const pageTwoButton = screen.getByRole('button', { name: 'Go to page 2' });
    fireEvent.click(pageTwoButton);

    expect(screen.getByTestId('case-card-child-6')).toBeInTheDocument();
    expect(screen.queryByTestId('case-card-child-1')).not.toBeInTheDocument();
  });
});

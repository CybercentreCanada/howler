/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tab: ({ label }: any) => <span>{label}</span>,
  Tabs: ({ children, onChange }: any) => (
    <div>
      {Array.isArray(children)
        ? children.map((child: any) =>
            child ? (
              <button key={child.props.value} onClick={() => onChange?.(null, child.props.value)}>
                {child}
              </button>
            ) : null
          )
        : children}
    </div>
  ),
  useTheme: () => ({ palette: { divider: '#ddd' } })
}));

vi.mock('components/elements/event/EventCard', () => ({
  default: ({ event }: any) => <div>{`event:${event.howler.id}`}</div>
}));

vi.mock('components/hooks/useRelatedRecords', () => ({
  default: () => [
    { __index: 'hit', howler: { id: 'hit-2' } },
    { __index: 'case', case_id: 'case-1' },
    { __index: 'event', howler: { id: 'event-1' } }
  ]
}));

vi.mock('lodash-es', () => ({
  groupBy: (records: any[], key: string) =>
    records.reduce(
      (acc, item) => {
        const group = item[key];
        acc[group] = [...(acc[group] ?? []), item];
        return acc;
      },
      {} as Record<string, any[]>
    )
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react-router', () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>
}));

vi.mock('utils/typeUtils', () => ({
  isCase: (record: any) => record?.__index === 'case',
  isEvent: (record: any) => record?.__index === 'event',
  isHit: (record: any) => record?.__index === 'hit'
}));

vi.mock('../case/CaseCard', () => ({
  default: ({ case: record }: any) => <div>{`case:${record.case_id}`}</div>
}));

vi.mock('../hit/HitCard', () => ({
  default: ({ id }: any) => <div>{`hit:${id}`}</div>
}));

vi.mock('../hit/HitLayout', () => ({
  HitLayout: { NORMAL: 'normal' }
}));

vi.mock('../hit/related/RelatedLink', () => ({
  default: ({ title, href }: any) => <div>{`${title}:${href}`}</div>
}));

import RecordRelated from './RecordRelated';

describe('RecordRelated', () => {
  it('renders links and switches between hit, case, and event related records', () => {
    render(
      <RecordRelated
        record={
          {
            __index: 'hit',
            howler: {
              id: 'hit-1',
              related: ['ref-1'],
              links: [{ title: 'Example', href: 'https://example.com' }]
            }
          } as any
        }
      />
    );

    expect(screen.getByText('Example:https://example.com')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('hit.related.tab.hit')[0]!);
    expect(screen.getByText('hit:hit-2')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('hit.related.tab.case')[0]!);
    expect(screen.getByText('case:case-1')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('hit.related.tab.event')[0]!);
    expect(screen.getByText('event:event-1')).toBeInTheDocument();
  });

  it('returns nothing when no record is provided', () => {
    const { container } = render(<RecordRelated record={undefined as any} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows related records, but no hit-only links, for an event', () => {
    const event: Event = {
      __index: 'event',
      timestamp: '2026-01-01T00:00:00Z',
      howler: { id: 'event-source', hash: 'abc', related: ['hit-2', 'case-1', 'event-1'] }
    };

    render(<RecordRelated record={event} />);

    expect(screen.queryByText('hit.related.tab.links')).not.toBeInTheDocument();
    expect(screen.getByText('hit:hit-2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('hit.related.tab.event'));
    expect(screen.getByText('event:event-1')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'event:event-1' })).toHaveAttribute('href', '/events/event-1');
  });

  it('switches away from a selected links tab when the source changes to an event', () => {
    const hit: Hit = {
      __index: 'hit',
      timestamp: '2026-01-01T00:00:00Z',
      howler: {
        id: 'hit-source',
        hash: 'abc',
        analytic: 'Analytic',
        assignment: 'unassigned',
        links: [{ title: 'Example', href: 'https://example.com' }]
      }
    };
    const event: Event = {
      __index: 'event',
      timestamp: '2026-01-01T00:00:00Z',
      howler: { id: 'event-source', hash: 'abc' }
    };
    const { rerender } = render(<RecordRelated record={hit} />);
    fireEvent.click(screen.getByText('hit.related.tab.links'));

    rerender(<RecordRelated record={event} />);

    expect(screen.queryByText('Example:https://example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('hit.related.tab.links')).not.toBeInTheDocument();
    expect(screen.getByText('hit:hit-2')).toBeInTheDocument();
  });
});

/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tab: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  Tabs: ({ children }: any) => <div>{children}</div>,
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
    records.reduce((acc, item) => {
      const group = item[key];
      acc[group] = [...(acc[group] ?? []), item];
      return acc;
    }, {} as Record<string, any[]>)
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
        record={{
          __index: 'hit',
          howler: {
            id: 'hit-1',
            related: ['ref-1'],
            links: [{ title: 'Example', href: 'https://example.com' }]
          }
        } as any}
      />
    );

    expect(screen.getByText('Example:https://example.com')).toBeInTheDocument();

    fireEvent.click(screen.getByText('hit.related.tab.hit'));
    expect(screen.getByText('hit:hit-2')).toBeInTheDocument();

    fireEvent.click(screen.getByText('hit.related.tab.case'));
    expect(screen.getByText('case:case-1')).toBeInTheDocument();

    fireEvent.click(screen.getByText('hit.related.tab.event'));
    expect(screen.getByText('event:event-1')).toBeInTheDocument();
  });

  it('returns nothing when no record is provided', () => {
    const { container } = render(<RecordRelated record={undefined as any} />);
    expect(container).toBeEmptyDOMElement();
  });
});

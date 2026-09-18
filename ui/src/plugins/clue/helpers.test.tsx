/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockGuessType = vi.hoisted(() => vi.fn());

vi.mock('@cccsaurora/clue-ui/components/EnrichedTypography', () => ({
  default: ({ type, value }: any) => <div>{`${type}:${value}`}</div>
}));

vi.mock('@cccsaurora/clue-ui/components/fetchers/Fetcher', () => ({
  default: ({ fetcherId, type, value }: any) => <div>{`${fetcherId}:${type}:${value}`}</div>
}));

vi.mock('@cccsaurora/clue-ui/components/group/Entry', () => ({
  default: ({ children, entry, selected }: any) => <div>{`${entry}:${selected}`}{children}</div>
}));

vi.mock('@cccsaurora/clue-ui/components/group/Group', () => ({
  default: ({ children, type }: any) => <div>{`${type}-group`}{children}</div>
}));

vi.mock('@cccsaurora/clue-ui/hooks/selectors', () => ({
  useClueEnrichSelector: () => mockGuessType
}));

vi.mock('@mui/material', () => ({
  Checkbox: ({ checked, onChange }: any) => <input aria-label="checkbox" checked={checked} onChange={event => onChange(event, !checked)} type="checkbox" />,
  Paper: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Table: ({ children }: any) => <table>{children}</table>,
  TableBody: ({ children }: any) => <tbody>{children}</tbody>,
  TableCell: ({ children }: any) => <td>{children}</td>,
  TableHead: ({ children }: any) => <thead>{children}</thead>,
  TableRow: ({ children }: any) => <tr>{children}</tr>
}));

vi.mock('components/elements/addons/layout/FlexOne', () => ({
  default: () => <div>flex</div>
}));

vi.mock('i18n', () => ({
  default: {
    t: (key: string) => key
  }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import HELPERS from './helpers';

describe('clue helpers', () => {
  it('renders clue helper errors and enriched values', () => {
    const clue = HELPERS.find(entry => entry.keyword === 'clue')!;

    render(clue.componentCallback?.(null, 'value') as any);
    expect(screen.getByText('markdown.error')).toBeInTheDocument();
    expect(screen.getByText('markdown.helpers.clue.arguments')).toBeInTheDocument();

    mockGuessType.mockReturnValue('ip');
    const { rerender } = render(clue.componentCallback?.('guess', '1.2.3.4') as any);
    expect(screen.getByText('ip:1.2.3.4')).toBeInTheDocument();

    mockGuessType.mockImplementation(() => {
      throw new Error('bad selector');
    });
    rerender(clue.componentCallback?.('guess', 'broken') as any);
    expect(screen.getByText('Error: bad selector')).toBeInTheDocument();
  });

  it('renders fetcher and clue group helper states', () => {
    const fetcher = HELPERS.find(entry => entry.keyword === 'fetcher')!;
    const clueGroup = HELPERS.find(entry => entry.keyword === 'clue_group')!;

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const { rerender } = render(fetcher.componentCallback?.({}, { hash: {} }) as any);
    expect(screen.getByText(/markdown.props.missing/)).toHaveTextContent('markdown.props.missing: type, value, fetcherId');
    expect(errorSpy).toHaveBeenCalledWith('Missing required props for fetcher helper');

    rerender(fetcher.componentCallback?.({}, { hash: { type: 'ip', value: '1.2.3.4', fetcherId: 'eml-lookup' } }) as any);
    expect(screen.getByText('email-lookup:ip:1.2.3.4')).toBeInTheDocument();

    rerender(clueGroup.componentCallback?.('bad', { hash: {} }) as any);
    expect(screen.getByText(/markdown.props.missing/)).toHaveTextContent('markdown.props.missing: values, type');

    rerender(clueGroup.componentCallback?.(['one', 'one', 'two'], { hash: { type: 'domain' } }) as any);
    expect(screen.getByText('domain-group')).toBeInTheDocument();
    expect(screen.getByText('one:false')).toBeInTheDocument();
    expect(screen.getByText('two:false')).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('checkbox')[0]);
    expect(screen.getByText('one:true')).toBeInTheDocument();
  });

  it('renders clue tables with enrichers, fetchers, and selection checkboxes', () => {
    const clueTable = HELPERS.find(entry => entry.keyword === 'clue_table')!;
    mockGuessType.mockReturnValue(undefined);

    render(
      clueTable.componentCallback?.(
        [
          { column: 'entity_name', row: '1', value: 'alpha', clue_type: 'guess', clue_entity: true, action_value: 'A' },
          { column: 'entity_type', row: '1', value: '1.2.3.4', clue_type: 'ip', clue_fetcher: 'geo', fetcher_width: '100px' },
          { column: 'notes', row: '2', value: 'freeform' }
        ],
        { hash: { clue_action_type: 'ip' } }
      ) as any
    );

    expect(screen.getByText('Entity Name')).toBeInTheDocument();
    expect(screen.getByText('Entity Type')).toBeInTheDocument();
    expect(screen.getByText('ip-group')).toBeInTheDocument();
    expect(screen.getByText('geo:ip:1.2.3.4')).toBeInTheDocument();
    expect(screen.getByText('freeform')).toBeInTheDocument();
    expect(screen.getByText('A:false')).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText('checkbox')[0]);
    expect(screen.getByText('A:true')).toBeInTheDocument();
  });
});

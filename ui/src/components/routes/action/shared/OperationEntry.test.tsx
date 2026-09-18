/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return { ...actual, Delete: () => <div>delete-icon</div> };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
  Chip: ({ label }: any) => <div>{label}</div>,
  Divider: () => <div>divider</div>,
  IconButton: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  ListItemText: ({ primary, secondary }: any) => <div>{`${primary}:${secondary}`}</div>,
  MenuItem: ({ children }: any) => <div>{children}</div>,
  Select: ({ onChange, children }: any) => <div><button onClick={() => onChange({ target: { value: 'op-2' } })}>change-operation</button>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: any) => <div>{md}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('utils/actionUtils', () => ({
  checkArgsAreFilled: (_step: any, values: string) => values !== '{}',
  operationReady: () => true
}));

vi.mock('./OperationStep', () => ({
  default: ({ step, setValues }: any) => (
    <div>
      <div>{`step:${Object.keys(step.args).join(',')}`}</div>
      <button onClick={() => setValues?.('{"foo":"bar"}')}>set-step-values</button>
    </div>
  )
}));

import OperationEntry from './OperationEntry';

describe('OperationEntry', () => {
  const makeOperations = () => [
    {
      id: 'op-1',
      title: 'First',
      description: { short: 'short-1', long: 'long-1' },
      triggers: ['manual'],
      steps: [{ args: { first: true } }, { args: { second: true } }],
      priority: 1
    },
    {
      id: 'op-2',
      title: 'Second',
      description: { short: 'short-2', long: 'long-2' },
      triggers: ['auto'],
      steps: [{ args: { only: true } }],
      priority: 2
    }
  ];

  it('renders editable operations, deletes entries, and forwards step updates', () => {
    const onChange = vi.fn();
    const onDelete = vi.fn();
    const operations = makeOperations();

    render(
      <OperationEntry
        query="status:open"
        operation={operations[0] as any}
        operations={operations as any}
        values={'{"first":"ok"}'}
        onChange={onChange}
        onDelete={onDelete}
      />
    );

    expect(screen.getByText('long-1')).toBeInTheDocument();
    expect(screen.getByText('route.actions.trigger.manual')).toBeInTheDocument();
    expect(screen.getByText('Second:short-2')).toBeInTheDocument();
    expect(screen.getByText('step:first')).toBeInTheDocument();
    expect(screen.getByText('step:second')).toBeInTheDocument();

    fireEvent.click(screen.getByText('change-operation'));
    expect(onChange).toHaveBeenCalledWith({ operation_id: 'op-2', data_json: '{}' });

    fireEvent.click(screen.getAllByText('set-step-values')[0]!);
    expect(onChange).toHaveBeenCalledWith({ operation_id: 'op-1', data_json: '{"foo":"bar"}' });

    fireEvent.click(screen.getByText('delete-icon'));
    expect(onDelete).toHaveBeenCalled();
  });

  it('returns null without an operation id and hides actions when readonly', () => {
    const operations = makeOperations();
    const { rerender, container } = render(
      <OperationEntry query="q" operation={{ id: undefined } as any} operations={operations as any} />
    );
    expect(container.textContent ?? '').toBe('');

    rerender(<OperationEntry query="q" operation={operations[0] as any} operations={operations as any} readonly values="{}" />);
    expect(screen.queryByText('delete-icon')).not.toBeInTheDocument();
    expect(screen.getByText('step:first')).toBeInTheDocument();
    expect(screen.queryByText('step:second')).not.toBeInTheDocument();
  });
});

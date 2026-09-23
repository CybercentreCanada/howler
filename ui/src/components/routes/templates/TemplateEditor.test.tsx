/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetHitFields = vi.hoisted(() => vi.fn().mockResolvedValue([{ key: 'field.one' }, { key: 'field.two' }]));
const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
const fieldContextToken = vi.hoisted(() => ({ name: 'field-context' }));

let configValue: any = {
  indexes: {
    hit: {
      'field.one': { description: 'Field one description\nextra' },
      'field.two': { description: 'Field two description' }
    }
  }
};

vi.mock('@dnd-kit/core', () => ({
  closestCorners: vi.fn(),
  DndContext: ({ children, onDragEnd }: any) => (
    <div>
      <button onClick={() => onDragEnd({ active: { id: 'field.one' }, over: { id: 'field.two' } })}>drag-end</button>
      {children}
    </div>
  )
}));

vi.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: any) => <div>{children}</div>,
  arrayMove: (items: string[], from: number, to: number) => {
    const next = [...items];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    return next;
  }
}));

vi.mock('@mui/icons-material', () => ({
  Add: () => <div>add-icon</div>
}));

vi.mock('@mui/material', () => ({
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/app/providers/FieldProvider', () => ({
  FieldContext: fieldContextToken
}));

vi.mock('components/elements/addons/search/phrase/Phrase', () => ({
  default: ({ value, onChange, onKeyDown }: any) => (
    <div>
      <input aria-label="phrase" value={value} onChange={e => onChange(e.target.value)} />
      <button onClick={() => onKeyDown?.({ isEnter: true })}>phrase-enter</button>
    </div>
  )
}));

vi.mock('lodash-es', () => ({
  get: (obj: any, path: string) => path.split('.').reduce((acc, key) => acc?.[key], obj),
  isObject: (value: any) => value != null && typeof value === 'object'
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('./TemplateDnD', () => ({
  default: ({ field, data, onRemove, tooltipTitle }: any) => (
    <div>
      <span>{`${field}:${data}:${tooltipTitle}`}</span>
      <button onClick={() => onRemove(field)}>remove-{field}</button>
    </div>
  )
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      if (context === fieldContextToken) return { getHitFields: mockGetHitFields };
      return actual.useContext(context);
    }
  };
});

import TemplateEditor from './TemplateEditor';

describe('TemplateEditor', () => {
  beforeEach(() => {
    mockGetHitFields.mockClear();
  });

  it('loads suggestions, adds and removes fields, and reorders fields', async () => {
    const onAdd = vi.fn();
    const onRemove = vi.fn();
    const setFields = vi.fn();

    render(
      <TemplateEditor
        hit={{ field: { one: { value: 1 } }, field2: 'x' } as any}
        fields={['field.one', 'field.two']}
        setFields={setFields}
        onRemove={onRemove}
        onAdd={onAdd}
      />
    );

    await waitFor(() => expect(mockGetHitFields).toHaveBeenCalled());
    expect(screen.getByText('field.one:{"value":1}:Field one description')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('phrase'), { target: { value: 'field.two' } });
    fireEvent.click(screen.getByText('button.add'));
    expect(onAdd).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('phrase'), { target: { value: 'field.one' } });
    fireEvent.click(screen.getByText('remove-field.one'));
    expect(onRemove).toHaveBeenCalledWith('field.one');

    fireEvent.change(screen.getByLabelText('phrase'), { target: { value: 'field.two' } });
    fireEvent.click(screen.getByText('phrase-enter'));
    expect(onAdd).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('phrase'), { target: { value: 'field.one' } });
    fireEvent.click(screen.getByText('drag-end'));
    expect(setFields).toHaveBeenCalledWith(['field.two', 'field.one']);
  });
});

/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { createMockCase } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockUpdate = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock('../hooks/useCase', () => ({
  default: ({ case: c }: { case: Case }) => ({
    case: c,
    update: mockUpdate,
    loading: false,
    missing: false
  })
}));

vi.mock('components/elements/display/ClassificationChip', () => ({
  default: () => <span id="classification-chip" />
}));

vi.mock('components/elements/display/Markdown', () => ({
  default: ({ md }: { md?: string }) => <div id="markdown-preview">{md}</div>
}));

vi.mock('components/elements/ThemedEditor', () => ({
  default: ({ id, value, onChange }: { id?: string; value?: string; onChange?: (value?: string) => void }) => (
    <textarea id={id ?? 'themed-editor'} value={value ?? ''} onChange={ev => onChange?.(ev.target.value)} />
  )
}));

const { default: MarkdownPage } = await import('./MarkdownPage');

describe('MarkdownPage', () => {
  let user: UserEvent;
  let markdownItem: Item;
  let _case: Case;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();

    markdownItem = {
      id: 'item-1',
      parent: null,
      type: 'markdown',
      name: 'Analyst Notes',
      value: 'Initial markdown value',
      classification: 'TLP:CLEAR'
    };

    _case = createMockCase({
      case_id: 'case-1',
      items: [
        markdownItem,
        {
          id: 'item-2',
          parent: null,
          type: 'markdown',
          name: 'Other Item',
          value: 'Keep this value'
        }
      ]
    });
  });

  it('renders read mode by default', () => {
    render(<MarkdownPage case={_case} item={markdownItem} />);

    expect(screen.getByText('Initial markdown value')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.getByRole('button', { name: 'edit' })).toBeInTheDocument();
  });

  it('enters edit mode and updates preview as content changes', async () => {
    render(<MarkdownPage case={_case} item={markdownItem} />);

    await user.click(screen.getByRole('button', { name: 'edit' }));

    const editor = screen.getByRole('textbox');
    expect(editor).toHaveValue('Initial markdown value');

    await user.clear(editor);
    await user.type(editor, 'Updated markdown preview');

    expect(screen.getByTestId('markdown-preview')).toHaveTextContent('Updated markdown preview');
  });

  it('cancels edits and restores the original item value', async () => {
    render(<MarkdownPage case={_case} item={markdownItem} />);

    await user.click(screen.getByRole('button', { name: 'edit' }));

    const editor = screen.getByRole('textbox');
    await user.clear(editor);
    await user.type(editor, 'Unsaved value');

    await user.click(screen.getByRole('button', { name: 'button.cancel' }));

    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.getByText('Initial markdown value')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'edit' }));
    expect(screen.getByRole('textbox')).toHaveValue('Initial markdown value');
  });

  it('saves edits through update and exits edit mode', async () => {
    render(<MarkdownPage case={_case} item={markdownItem} />);

    await user.click(screen.getByRole('button', { name: 'edit' }));

    const editor = screen.getByRole('textbox');
    await user.clear(editor);
    await user.type(editor, 'Persisted value');

    await user.click(screen.getByRole('button', { name: 'button.save' }));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledOnce();
    });

    expect(mockUpdate).toHaveBeenCalledWith({
      items: [
        {
          id: 'item-1',
          parent: null,
          type: 'markdown',
          name: 'Analyst Notes',
          value: 'Persisted value',
          classification: 'TLP:CLEAR'
        },
        {
          id: 'item-2',
          parent: null,
          type: 'markdown',
          name: 'Other Item',
          value: 'Keep this value'
        }
      ]
    });

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).toBeNull();
    });
    expect(screen.getByText('Persisted value')).toBeInTheDocument();
  });
});

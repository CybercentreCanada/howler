/// <reference types="vitest" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const mockShowErrorMessage = vi.hoisted(() => vi.fn());

vi.mock('@mui/icons-material', async importOriginal => {
  const actual = await importOriginal<typeof import('@mui/icons-material')>();
  return {
    ...actual,
    Check: () => <div>check-icon</div>,
    Close: () => <div>close-icon</div>,
    Delete: () => <div>delete-icon</div>,
    Edit: () => <div>edit-icon</div>
  };
});

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Checkbox: ({ checked, onChange }: any) => <input aria-label="checkbox" type="checkbox" checked={checked} onChange={onChange} />,
  CircularProgress: () => <div>loading</div>,
  IconButton: ({ children, onClick, disabled }: any) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  Slider: ({ value, onChange }: any) => <input aria-label="slider" type="range" value={value} onChange={e => onChange(null, Number(e.target.value))} />,
  Stack: ({ children }: any) => <div>{children}</div>,
  TableCell: ({ children }: any) => <div>{children}</div>,
  TableRow: ({ children }: any) => <div>{children}</div>,
  TextField: ({ value, onChange, onKeyDown, label, type, error }: any) => (
    <label>
      {label ?? type ?? 'text'}
      <input aria-label={label ?? type ?? 'text'} value={String(value ?? '')} onChange={onChange} onKeyDown={onKeyDown} data-error={String(error)} />
    </label>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/hooks/useMySnackbar', () => ({
  default: () => ({ showErrorMessage: mockShowErrorMessage })
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import EditRow from './EditRow';

describe('EditRow', () => {
  it('edits text values and closes on escape when unchanged', async () => {
    const onEdit = vi.fn(async () => undefined);
    render(<EditRow titleKey="title" descriptionKey="description" value="current" onEdit={onEdit} />);

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('text'), { target: { value: 'updated' } });
    fireEvent.click(screen.getByText('check-icon'));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith('updated'));

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.keyDown(screen.getByLabelText('text'), { key: 'Escape' });
    expect(screen.queryByLabelText('text')).not.toBeInTheDocument();
    expect(screen.getByText('description')).toBeInTheDocument();
  });

  it('validates passwords and supports optional delete', async () => {
    const onEdit = vi.fn(async () => undefined);
    render(<EditRow titleKey="password.title" value="secret" type="password" onEdit={onEdit} optional />);

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('password'), { target: { value: 'next-secret' } });
    fireEvent.change(screen.getByLabelText('password.confirm'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByText('check-icon'));
    expect(mockShowErrorMessage).toHaveBeenCalledWith('password.match');

    fireEvent.change(screen.getByLabelText('password.confirm'), { target: { value: 'next-secret' } });
    fireEvent.click(screen.getByText('check-icon'));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith('next-secret'));

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.click(screen.getByText('delete-icon'));
    await waitFor(() => expect(onEdit).toHaveBeenCalledWith(undefined));
  });

  it('applies checkbox and range edits with validation', async () => {
    const checkboxEdit = vi.fn(async () => undefined);
    const rangeEdit = vi.fn(async () => undefined);

    const { rerender } = render(<EditRow titleKey="checkbox.title" value={false} type="checkbox" onEdit={checkboxEdit} />);
    fireEvent.click(screen.getByLabelText('checkbox'));
    await waitFor(() => expect(checkboxEdit).toHaveBeenCalledWith('true'));

    rerender(
      <EditRow titleKey="range.title" value={10} type="range" min={5} max={20} onEdit={rangeEdit} valueLabelFormat={value => `${value}%`} />
    );
    expect(screen.getByText('10%')).toBeInTheDocument();
    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('slider'), { target: { value: '15' } });
    fireEvent.click(screen.getByText('check-icon'));
    await waitFor(() => expect(rangeEdit).toHaveBeenCalledWith('15'));
  });

  it('tracks validation errors and failOnValidate behavior for text and numbers', () => {
    const onEdit = vi.fn(async () => undefined);
    const { unmount } = render(
      <EditRow titleKey="text.title" value="alpha" onEdit={onEdit} validate={value => value !== 'bad'} />
    );

    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('text'), { target: { value: 'bad' } });
    expect(screen.getByLabelText('text')).toHaveAttribute('data-error', 'true');

    unmount();
    render(
      <EditRow titleKey="number.title" value={5} type="number" min={2} max={10} onEdit={onEdit} failOnValidate />
    );
    fireEvent.click(screen.getByText('edit-icon'));
    fireEvent.change(screen.getByLabelText('number'), { target: { value: '1' } });
    expect(screen.getByLabelText('number')).toHaveValue('5');
  });
});

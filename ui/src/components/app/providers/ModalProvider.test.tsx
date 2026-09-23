/// <reference types="vitest" />
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('components/elements/display/modals/ConfirmDeleteModal', () => ({
  default: ({ onConfirm, preferDelete, preferCancel }: any) => (
    <button onClick={onConfirm}>{`confirm:${String(preferDelete)}:${String(preferCancel)}`}</button>
  )
}));

import ModalProvider, { ModalContext } from './ModalProvider';

const Consumer = () => {
  const modal = useContext(ModalContext);
  return (
    <div>
      <button onClick={() => modal.showModal(<div>modal-body</div>, { disableClose: true, maxWidth: 'xl' })}>show</button>
      <button onClick={() => modal.withConfirmDeleteModal(vi.fn(), true, false)}>confirm-wrapper</button>
      <button onClick={() => modal.close()}>close</button>
      <div>{String(modal.options?.disableClose)}</div>
      <div>{modal.content as any}</div>
    </div>
  );
};

describe('ModalProvider', () => {
  it('shows modal content, resets options, and closes', async () => {
    render(
      <ModalProvider>
        <Consumer />
      </ModalProvider>
    );

    fireEvent.click(screen.getByText('show'));
    expect(screen.getByText('modal-body')).toBeInTheDocument();
    expect(screen.getAllByText('true')[0]).toBeInTheDocument();

    fireEvent.click(screen.getByText('close'));
    await act(async () => {});
    expect(screen.queryByText('modal-body')).not.toBeInTheDocument();
  });

  it('builds confirm-delete modal wrappers', () => {
    const onConfirm = vi.fn();
    const TestConsumer = () => {
      const modal = useContext(ModalContext);
      return (
        <div>
          <button onClick={() => modal.withConfirmDeleteModal(onConfirm, true, false)}>show-confirm</button>
          <div>{modal.content as any}</div>
        </div>
      );
    };

    render(
      <ModalProvider>
        <TestConsumer />
      </ModalProvider>
    );

    fireEvent.click(screen.getByText('show-confirm'));
    fireEvent.click(screen.getByText('confirm:true:false'));
    expect(onConfirm).toHaveBeenCalled();
  });
});

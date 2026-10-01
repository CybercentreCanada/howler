/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@tui/core', () => ({
  PageContent: ({ children }: any) => <div>{children}</div>
}));

vi.mock('@mui/material', () => ({
  Drawer: ({ children, open, onClose }: any) => (
    <div data-open={String(open)}>
      <button onClick={onClose}>close-drawer</button>
      {children}
    </div>
  ),
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => `translated:${key}` })
}));

import AppDrawerProvider, { AppDrawerContext } from './AppDrawerProvider';

const Consumer = () => {
  const drawer = useContext(AppDrawerContext);
  return (
    <div>
      <button
        onClick={() =>
          drawer.open({ titleKey: 'drawer.title', children: <div>drawer-body</div>, onClosed: vi.fn() } as any)
        }
      >
        open
      </button>
      <button onClick={() => drawer.close()}>close</button>
    </div>
  );
};

describe('AppDrawerProvider', () => {
  it('opens and closes the drawer with translated content', () => {
    const onClosed = vi.fn();
    const TestConsumer = () => {
      const drawer = useContext(AppDrawerContext);
      return (
        <button
          onClick={() => drawer.open({ titleKey: 'drawer.title', children: <div>drawer-body</div>, onClosed } as any)}
        >
          open
        </button>
      );
    };

    render(
      <AppDrawerProvider>
        <TestConsumer />
      </AppDrawerProvider>
    );

    expect(screen.getByText('close-drawer').parentElement).toHaveAttribute('data-open', 'false');
    fireEvent.click(screen.getByText('open'));
    expect(screen.getByText('close-drawer').parentElement).toHaveAttribute('data-open', 'true');
    expect(screen.getByText('translated:drawer.title')).toBeInTheDocument();
    expect(screen.getByText('drawer-body')).toBeInTheDocument();

    fireEvent.click(screen.getByText('close-drawer'));
    expect(onClosed).toHaveBeenCalled();
  });

  it('exposes default no-op context methods before open is called', () => {
    render(
      <AppDrawerProvider>
        <Consumer />
      </AppDrawerProvider>
    );

    fireEvent.click(screen.getByText('close'));
    expect(screen.getByText('close-drawer').parentElement).toHaveAttribute('data-open', 'false');
  });
});

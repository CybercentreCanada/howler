/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@mui/material', () => ({
  Badge: ({ children, badgeContent }: any) => <div>{badgeContent}{children}</div>,
  Button: ({ children, onClick, disabled }: any) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  FormControl: ({ children }: any) => <div>{children}</div>,
  FormControlLabel: ({ label, onClick }: any) => <button onClick={onClick}>{label}</button>,
  FormLabel: ({ children }: any) => <div>{children}</div>,
  Radio: () => <div>radio</div>,
  RadioGroup: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Tooltip: ({ children }: any) => <>{children}</>,
  styled: (_component: any) => (styles: any) => {
    void styles;
    return ({ children, badgeContent }: any) => <div>{badgeContent}{children}</div>;
  }
}));

vi.mock('@mui/material/colors', () => ({
  blueGrey: { 400: '#789' }
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import { HitShortcuts } from '../HitShortcuts';
import ButtonActions from './ButtonActions';

describe('ButtonActions', () => {
  it('renders actions, assessments, and votes with shortcut badges and handles clicks', () => {
    const actionFn = vi.fn();
    const assessFn = vi.fn();
    const voteFn = vi.fn();

    render(
      <ButtonActions
        actions={[
          { type: 'action', name: 'Transition', actionFunction: actionFn, key: 'T' },
          { type: 'assessment', name: 'legitimate', actionFunction: assessFn, key: 'A' },
          { type: 'vote', name: 'Benign', actionFunction: voteFn, key: 'Q' }
        ] as any}
        loading={false}
        orientation="horizontal"
        shortcuts={HitShortcuts.SHORTCUTS_HINT}
        currentVote="benign"
      />
    );

    expect(screen.getByText('hit.details.actions.action')).toBeInTheDocument();
    expect(screen.getByText('hit.details.actions.assessment')).toBeInTheDocument();
    expect(screen.getByText('hit.details.actions.vote')).toBeInTheDocument();
    expect(screen.getByText('T')).toBeInTheDocument();
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('Q')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Transition'));
    fireEvent.click(screen.getByText('legitimate'));
    fireEvent.click(screen.getByText('Benign'));

    expect(actionFn).toHaveBeenCalled();
    expect(assessFn).toHaveBeenCalled();
    expect(voteFn).toHaveBeenCalled();
  });
});

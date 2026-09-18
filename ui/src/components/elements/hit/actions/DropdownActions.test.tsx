/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
let configValue: any = {};

vi.mock('@mui/material', () => ({
  FormControl: ({ children, disabled }: any) => <fieldset disabled={disabled}>{children}</fieldset>,
  formControlClasses: { root: 'MuiFormControl-root' },
  Grid: ({ children }: any) => <div>{children}</div>,
  InputLabel: ({ children }: any) => <label>{children}</label>,
  MenuItem: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  Select: ({ children }: any) => <div>{children}</div>,
  Skeleton: () => <div>loading</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  Typography: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('lodash-es', () => ({
  capitalize: (value: string) => value.charAt(0).toUpperCase() + value.slice(1)
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return { config: configValue };
      return actual.useContext(context);
    }
  };
});

import DropdownActions from './DropdownActions';

describe('DropdownActions', () => {
  it('renders skeletons without lookups and action menus with lookups', () => {
    const actionFn = vi.fn();
    const assessFn = vi.fn();
    const voteFn = vi.fn();

    configValue = {};
    const { rerender } = render(
      <DropdownActions actions={[]} currentAssessment="" currentStatus="open" currentVote="" loading={false} orientation="horizontal" />
    );

    expect(screen.getAllByText('loading')).toHaveLength(3);

    configValue = { lookups: { any: true } };
    rerender(
      <DropdownActions
        actions={[
          { type: 'action', name: 'Transition', actionFunction: actionFn },
          { type: 'assessment', name: 'false-positive', actionFunction: assessFn },
          { type: 'vote', name: 'Benign', actionFunction: voteFn }
        ] as any}
        currentAssessment=""
        currentStatus="open"
        currentVote=""
        loading={false}
        orientation="vertical"
      />
    );

    fireEvent.click(screen.getByText('Transition'));
    fireEvent.click(screen.getByText('False Positive'));
    fireEvent.click(screen.getByText('Benign'));

    expect(actionFn).toHaveBeenCalled();
    expect(assessFn).toHaveBeenCalled();
    expect(voteFn).toHaveBeenCalled();
  });
});

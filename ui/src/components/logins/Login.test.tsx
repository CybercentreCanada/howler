/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const apiConfigContextToken = vi.hoisted(() => ({ name: 'api-config-context' }));
let apiConfigValue: any = { loaded: false, config: {} };

vi.mock('@mui/material', () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  CircularProgress: () => <div>loading</div>,
  Container: ({ children }: any) => <div>{children}</div>,
  Stack: ({ children }: any) => <div>{children}</div>,
  styled: (component: any) => () => component
}));

vi.mock('@tui/core', () => ({
  PageCardCentered: ({ children }: any) => <div>{children}</div>
}));

vi.mock('branding/AppBrand', () => ({
  AppBrand: () => <div>brand</div>
}));

vi.mock('components/app/providers/ApiConfigProvider', () => ({
  ApiConfigContext: apiConfigContextToken
}));

vi.mock('components/elements/display/TextDivider', () => ({
  default: () => <div>divider</div>
}));

vi.mock('./auth/OAuthLogin', () => ({
  default: ({ providers }: any) => <div>{providers.join(',')}</div>
}));

vi.mock('./auth/UserPassLogin', () => ({
  default: () => <div>userpass</div>
}));

vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useContext: (context: any) => {
      if (context === apiConfigContextToken) return apiConfigValue;
      return actual.useContext(context);
    }
  };
});

import LoginScreen from './Login';

describe('Login', () => {
  it('shows a loading indicator until config is loaded', () => {
    apiConfigValue = { loaded: false, config: {} };
    render(<LoginScreen />);
    expect(screen.getByText('loading')).toBeInTheDocument();
  });

  it('renders internal and oauth login options from config', () => {
    apiConfigValue = {
      loaded: true,
      config: {
        configuration: {
          auth: {
            internal: { enabled: true },
            oauth_providers: ['azure', 'google']
          }
        }
      }
    };
    render(<LoginScreen />);
    expect(screen.getByText('userpass')).toBeInTheDocument();
    expect(screen.getByText('divider')).toBeInTheDocument();
    expect(screen.getByText('azure,google')).toBeInTheDocument();
  });
});

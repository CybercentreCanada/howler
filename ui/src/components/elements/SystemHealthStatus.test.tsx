import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, vi } from 'vitest';
import type { SystemStatus } from '../hooks/useFetchHealth';
import * as useFetchHealth from '../hooks/useFetchHealth';
import SystemHealthStatus from './SystemHealthStatus';

describe('SystemHealthStatus component', () => {
  const useFetchHealthSpy = vi.spyOn(useFetchHealth, 'default');
  const allHealthyItems: SystemStatus[] = [
    {
      name: 'Fjallraven',
      healthy: true,
      importance: 'optional'
    },
    {
      name: 'Vargulven',
      healthy: true,
      importance: 'optional'
    }
  ];

  const warningItems: SystemStatus[] = [
    {
      name: 'Fjallraven',
      healthy: false,
      importance: 'optional'
    },
    {
      name: 'Vargulven',
      healthy: true,
      importance: 'optional'
    }
  ];

  const errorItems: SystemStatus[] = [
    {
      name: 'Fjallraven',
      healthy: true,
      importance: 'optional'
    },
    {
      name: 'Vargulven',
      healthy: false,
      importance: 'critical'
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    useFetchHealthSpy.mockReturnValue({
      healthStatus: allHealthyItems,
      loading: false
    });
  });

  it('should return the initial values for data and loading', () => {
    render(<SystemHealthStatus />);
    const rootElement = screen.queryByTestId('healthy-status-root');
    expect(rootElement).toBeInTheDocument();
    const element = screen.queryByTestId('healthy-status-root');
    expect(element).toHaveStyle('background-color: rgb(27, 94, 32)');
    const popoverElement = screen.queryByTestId('mouse-over-popover');
    expect(popoverElement).not.toBeInTheDocument();
  });

  it('should have loading element', () => {
    useFetchHealthSpy.mockReturnValue({
      healthStatus: [],
      loading: true
    });
    render(<SystemHealthStatus />);
    const rootElement = screen.queryByTestId('healthy-status-loading');
    expect(rootElement).toBeInTheDocument();
  });

  it('shows popout with healthstatus when hovered', () => {
    render(<SystemHealthStatus />);
    const rootElement = screen.getByTestId('healthy-status-root');
    expect(rootElement).toBeInTheDocument();
    act(() => {
      fireEvent.mouseEnter(rootElement);
    });
    const popoverElement = screen.getByTestId('mouse-over-popover');
    expect(popoverElement).toBeInTheDocument();
    const fjallravenText = screen.getByText('healthcheck.plugin.Fjallraven');
    expect(fjallravenText).toBeInTheDocument();
    const fjallravenCheck = screen.getByTestId('healthy-plugin-check-Fjallraven');
    expect(fjallravenCheck).toBeInTheDocument();
    const vargulvenText = screen.getByText('healthcheck.plugin.Vargulven');
    expect(vargulvenText).toBeInTheDocument();
    const vargulvenCheck = screen.getByTestId('healthy-plugin-check-Vargulven');
    expect(vargulvenCheck).toBeInTheDocument();
  });

  it('shows popout with healthstatus when hovered and then disappear', () => {
    render(<SystemHealthStatus />);
    const rootElement = screen.getByTestId('healthy-status-root');
    expect(rootElement).toBeInTheDocument();
    act(() => {
      fireEvent.mouseEnter(rootElement);
    });
    const popoverElement2 = screen.queryByTestId('mouse-over-popover');
    expect(popoverElement2).toBeInTheDocument();
    act(() => {
      fireEvent.mouseLeave(rootElement);
    });

    waitFor(() => expect(screen.queryByTestId('mouse-over-popover')).not.toBeInTheDocument());
  });

  it('should have critically unhealthy element', () => {
    useFetchHealthSpy.mockReturnValue({
      healthStatus: errorItems,
      loading: false
    });
    render(<SystemHealthStatus />);
    const unhealthyText = screen.queryByText('healthcheck.unhealthy');
    expect(unhealthyText).toBeInTheDocument();
    const element = screen.queryByTestId('healthy-status-root');
    expect(element).toHaveStyle('background-color: rgb(198, 40, 40)');
  });

  it('should have warning unhealthy element', () => {
    useFetchHealthSpy.mockReturnValue({
      healthStatus: warningItems,
      loading: false
    });
    render(<SystemHealthStatus />);
    const unhealthyText = screen.queryByText('healthcheck.unhealthy');
    expect(unhealthyText).toBeInTheDocument();
    const element = screen.queryByTestId('healthy-status-root');
    expect(element).toHaveStyle('background-color: rgb(230, 81, 0)');
  });
});

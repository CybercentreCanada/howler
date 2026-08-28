import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AnalyticLink from './AnalyticLink';

const getMatchingAnalytic = vi.hoisted(() => vi.fn());

vi.mock('components/app/hooks/useMatchers', () => ({
  default: () => ({ getMatchingAnalytic })
}));

describe('AnalyticLink', () => {
  beforeEach(() => {
    getMatchingAnalytic.mockResolvedValue({ analytic_id: 'analytic-id' });
  });

  it('renders an isolated link button when the analytic is resolved', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const hit = { howler: { analytic: 'Analytic Name', detection: 'Detection Name' } } as any;

    render(
      <BrowserRouter>
        <div onClick={onClick}>
          <AnalyticLink hit={hit} />
        </div>
      </BrowserRouter>
    );

    const link = await screen.findByRole('link');

    expect(link).toHaveAttribute('href', '/analytics/analytic-id');
    expect(screen.getByRole('heading')).toHaveTextContent('Analytic Name > Detection Name');

    await user.click(link);

    expect(onClick).not.toHaveBeenCalled();
  });
});

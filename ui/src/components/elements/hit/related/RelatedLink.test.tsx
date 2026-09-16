import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import RelatedLink from './RelatedLink';

describe('RelatedLink', () => {
  it('renders dense links as native links without opening them through the card handler', async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    render(
      <RelatedLink title="Example" href="https://example.test/pivot" target="_blank" rel="noopener noreferrer" dense>
        <span>Icon</span>
      </RelatedLink>
    );

    const link = screen.getByRole('link', { name: /example/i });
    expect(link).toHaveAttribute('href', 'https://example.test/pivot');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');

    await user.click(link);

    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });

  it('renders dense secondary content and a trailing action outside the link', () => {
    render(
      <RelatedLink
        title="Example"
        href="https://example.test/pivot"
        dense
        secondary={<span>Details</span>}
        action={<button type="button">Settings</button>}
      />
    );

    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Settings' }).closest('a')).toBeNull();
  });

  it('renders regular links as a single keyboard-accessible link', () => {
    render(
      <MemoryRouter>
        <RelatedLink title="Example" href="https://example.test/pivot" target="_blank" rel="noopener noreferrer">
          <span>Icon</span>
        </RelatedLink>
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /example/i });
    expect(link).toHaveAttribute('href', 'https://example.test/pivot');
    expect(link.closest('.MuiCard-root')).not.toBeNull();
  });
});

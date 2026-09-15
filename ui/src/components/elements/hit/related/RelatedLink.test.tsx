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

  it('preserves the card click behavior for regular links', async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    const { container } = render(
      <MemoryRouter>
        <RelatedLink title="Example" href="https://example.test/pivot" target="_blank" rel="noopener noreferrer">
          <span>Icon</span>
        </RelatedLink>
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /example/i });
    expect(link).toHaveAttribute('href', 'https://example.test/pivot');
    expect(link.closest('.MuiCard-root')).not.toBeNull();

    await user.click(container.querySelector('.MuiCard-root')!);

    expect(open).toHaveBeenCalledWith('https://example.test/pivot', '_blank');
    open.mockRestore();
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RelatedLink from './RelatedLink';

describe('RelatedLink', () => {
  it.each([
    ['default', {}],
    ['dense', { dense: true }],
    ['with card', { withCard: true }]
  ])('renders the %s variant as a native link', async (_variant, props) => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    render(
      <RelatedLink
        title="Example"
        href="https://example.test/pivot"
        target="_blank"
        rel="noopener noreferrer"
        {...props}
      >
        <span>Icon</span>
      </RelatedLink>
    );

    const link = screen.getByRole('link', { name: /example/i });
    expect(link).toHaveAttribute('href', 'https://example.test/pivot');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');

    await user.click(link);

    expect(open).not.toHaveBeenCalled();
  });
});

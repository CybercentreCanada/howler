/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import Image from './Image';

describe('Image', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
  });

  describe('thumbnail rendering', () => {
    it('renders an img element', () => {
      const { container } = render(<Image src="test.png" alt="a photo" />);
      expect(container.querySelector('img')).toBeInTheDocument();
    });

    it('forwards src and alt to the img element', () => {
      const { container } = render(<Image src="test.png" alt="a photo" />);
      const img = container.querySelector('img');
      expect(img).toHaveAttribute('src', 'test.png');
      expect(img).toHaveAttribute('alt', 'a photo');
    });

    it('applies cursor: pointer to the thumbnail', () => {
      const { container } = render(<Image src="test.png" />);
      expect(container.querySelector('img')).toHaveStyle({ cursor: 'pointer' });
    });

    it('merges provided style with cursor: pointer', () => {
      const { container } = render(<Image src="test.png" style={{ opacity: 0.5 }} />);
      const img = container.querySelector('img');
      expect(img).toHaveStyle({ cursor: 'pointer', opacity: '0.5' });
    });
  });

  describe('modal behaviour', () => {
    it('does not show the modal initially', () => {
      render(<Image src="test.png" />);
      expect(screen.queryByRole('presentation')).toBeNull();
    });

    it('opens the modal when the thumbnail is clicked', async () => {
      const { container } = render(<Image src="test.png" />);
      const thumbnail = container.querySelector('img');
      await user.click(thumbnail);
      await waitFor(() => {
        expect(screen.getByRole('presentation')).toBeInTheDocument();
      });
    });

    it('shows an enlarged image inside the modal', async () => {
      const { container } = render(<Image src="test.png" />);
      const thumbnail = container.querySelector('img');
      await user.click(thumbnail);
      await waitFor(() => {
        // MUI Modal renders into a portal outside container, so query document
        const images = document.querySelectorAll('img');
        // thumbnail + modal enlarged copy
        expect(images).toHaveLength(2);
        expect(images[1]).toHaveStyle({ maxWidth: '70vw', maxHeight: '70vh' });
      });
    });

    it('closes the modal when the close button is clicked', async () => {
      const { container } = render(<Image src="test.png" />);
      const thumbnail = container.querySelector('img');

      await user.click(thumbnail);
      await waitFor(() => expect(screen.getByRole('presentation')).toBeInTheDocument());

      const closeButton = screen.getByRole('button');
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByRole('presentation')).toBeNull();
      });
    });

    it('closes the modal via the onClose handler (Escape key)', async () => {
      const { container } = render(<Image src="test.png" />);
      const thumbnail = container.querySelector('img');

      await user.click(thumbnail);
      await waitFor(() => expect(screen.getByRole('presentation')).toBeInTheDocument());

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByRole('presentation')).toBeNull();
      });
    });
  });
});

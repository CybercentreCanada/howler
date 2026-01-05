/// <reference types="vitest" />
import { Info } from '@mui/icons-material';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { vi } from 'vitest';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

import ChipPopper from './ChipPopper';

describe('ChipPopper', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render chip with icon and label', () => {
      render(
        <ChipPopper icon={<Info id="chip-icon" />} label="Test Label">
          <div>Content</div>
        </ChipPopper>
      );

      expect(screen.getByTestId('chip-icon')).toBeInTheDocument();
      expect(screen.getByText('Test Label')).toBeInTheDocument();
    });

    it('should render chip with complex label', () => {
      render(
        <ChipPopper
          icon={<Info />}
          label={
            <div>
              <span>Complex</span> <strong>Label</strong>
            </div>
          }
        >
          <div>Content</div>
        </ChipPopper>
      );

      expect(screen.getByText('Complex')).toBeInTheDocument();
      expect(screen.getByText('Label')).toBeInTheDocument();
    });

    it('should not show popper content initially', () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div id="popper-content">Content</div>
        </ChipPopper>
      );

      // Content should not be visible initially
      expect(screen.queryByTestId('popper-content')).toBeNull();
    });
  });

  describe('Toggle Behavior', () => {
    it('should show popper content when chip is clicked', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div id="popper-content">Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('popper-content')).toBeVisible();
      });
    });

    it('should hide popper content when chip is clicked again', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div id="popper-content">Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');

      // Open
      await user.click(chip);
      await waitFor(() => {
        expect(screen.getByTestId('popper-content')).toBeVisible();
      });

      // Close
      await user.click(chip);
      await waitFor(() => {
        expect(screen.queryByTestId('popper-content')).toBeNull();
      });
    });

    it('should call onToggle callback when toggled', async () => {
      const onToggle = vi.fn();

      render(
        <ChipPopper icon={<Info />} label="Test" onToggle={onToggle}>
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');

      await user.click(chip);
      expect(onToggle).toHaveBeenCalledWith(true);

      await user.click(chip);
      expect(onToggle).toHaveBeenCalledWith(false);

      expect(onToggle).toHaveBeenCalledTimes(2);
    });

    it('should stop event propagation when chip is clicked', async () => {
      const parentClickHandler = vi.fn();

      render(
        <div onClick={parentClickHandler}>
          <ChipPopper icon={<Info />} label="Test">
            <div>Content</div>
          </ChipPopper>
        </div>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      expect(parentClickHandler).not.toHaveBeenCalled();
    });
  });

  describe('Click Away Behavior', () => {
    it('should close popper when clicking away', async () => {
      render(
        <div>
          <ChipPopper icon={<Info />} label="Test">
            <div id="popper-content">Content</div>
          </ChipPopper>
          <button id="outside-button">Outside</button>
        </div>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('popper-content')).toBeVisible();
      });

      // Click outside
      const outsideButton = screen.getByTestId('outside-button');
      await user.click(outsideButton);

      await waitFor(() => {
        expect(screen.queryByTestId('popper-content')).toBeNull();
      });
    });

    it('should call onToggle when clicking away', async () => {
      const onToggle = vi.fn();

      render(
        <div>
          <ChipPopper icon={<Info />} label="Test" onToggle={onToggle}>
            <div>Content</div>
          </ChipPopper>
          <button id="outside-button">Outside</button>
        </div>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      expect(onToggle).toHaveBeenCalledWith(true);
      onToggle.mockClear();

      // Click outside
      const outsideButton = screen.getByTestId('outside-button');
      await user.click(outsideButton);

      expect(onToggle).toHaveBeenCalledWith(false);
    });
  });

  describe('Props Customization', () => {
    it('should apply custom chip props', () => {
      render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            chip: {
              color: 'primary',
              variant: 'outlined',
              id: 'custom-chip'
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByTestId('custom-chip');
      expect(chip).toHaveClass('MuiChip-colorPrimary');
      expect(chip).toHaveClass('MuiChip-outlined');
    });

    it('should apply custom chip sx prop', () => {
      const { container } = render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            chip: {
              sx: { backgroundColor: 'red' }
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = container.querySelector('.MuiChip-root');
      expect(window.getComputedStyle(chip).getPropertyValue('background-color')).toBe('rgb(255, 0, 0)');
    });

    it('should apply custom paper props', async () => {
      render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            paper: {
              elevation: 8,
              id: 'custom-paper'
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const paper = screen.getByTestId('custom-paper');
        expect(paper).toBeInTheDocument();
        expect(paper).toHaveClass('MuiPaper-elevation8');
      });
    });

    it('should apply custom paper sx prop', async () => {
      const { container } = render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            paper: {
              sx: { backgroundColor: 'blue' }
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const paper = container.querySelector('.MuiPaper-root');
        expect(window.getComputedStyle(paper).getPropertyValue('background-color')).toBe('rgb(0, 0, 255)');
      });
    });

    it('should use custom placement', async () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test" placement="bottom-end">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const popper = container.querySelector('[data-popper-placement]');
        expect(popper).toHaveAttribute('data-popper-placement', 'bottom-end');
      });
    });

    it('should use custom minWidth when provided', async () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test" minWidth="500px">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const popper = container.querySelector('.MuiPopper-root');
        expect(popper).toHaveStyle({ minWidth: '500px' });
      });
    });

    it('should default to chip width when minWidth not provided', async () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const popper = container.querySelector('.MuiPopper-root');
        expect(popper).toBeInTheDocument();
      });
    });
  });

  describe('Styling', () => {
    it('should apply border radius transition styles to chip', () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = container.querySelector('.MuiChip-root');
      expect(chip).toHaveStyle({ position: 'relative', zIndex: '1' });
    });

    it('should apply rounded corner styles when popper is closed', () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = container.querySelector('.MuiChip-root');
      // Should have all corners rounded when closed
      expect(chip).not.toHaveStyle({
        borderBottomLeftRadius: '0',
        borderBottomRightRadius: '0'
      });
    });

    it('should remove bottom border radius when popper is open', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(chip).toHaveStyle({
          borderBottomLeftRadius: '0',
          borderBottomRightRadius: '0'
        });
      });
    });

    it('should apply top border radius 0 to paper', async () => {
      const { container } = render(
        <ChipPopper icon={<Info />} label="Test">
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const paper = container.querySelector('.MuiPaper-root');
        expect(paper).toHaveStyle({
          borderTopLeftRadius: '0',
          borderTopRightRadius: '0'
        });
      });
    });
  });

  describe('Children Rendering', () => {
    it('should render children content inside popper', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div id="child-1">Child 1</div>
          <div id="child-2">Child 2</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('child-1')).toBeVisible();
        expect(screen.getByTestId('child-2')).toBeVisible();
      });
    });

    it('should render complex children components', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div>
            <input id="test-input" type="text" />
            <button id="test-button">Click me</button>
          </div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('test-input')).toBeVisible();
        expect(screen.getByTestId('test-button')).toBeVisible();
      });
    });

    it('should allow interaction with children', async () => {
      const buttonClick = vi.fn();

      render(
        <ChipPopper icon={<Info />} label="Test">
          <button id="child-button" onClick={buttonClick}>
            Click me
          </button>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('child-button')).toBeVisible();
      });

      const button = screen.getByTestId('child-button');
      await user.click(button);

      expect(buttonClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid toggling', async () => {
      const onToggle = vi.fn();

      render(
        <ChipPopper icon={<Info />} label="Test" onToggle={onToggle}>
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');

      // Rapidly toggle multiple times
      await user.click(chip);
      await user.click(chip);
      await user.click(chip);
      await user.click(chip);

      expect(onToggle).toHaveBeenCalledTimes(4);
      expect(onToggle).toHaveBeenNthCalledWith(1, true);
      expect(onToggle).toHaveBeenNthCalledWith(2, false);
      expect(onToggle).toHaveBeenNthCalledWith(3, true);
      expect(onToggle).toHaveBeenNthCalledWith(4, false);
    });

    it('should work without onToggle callback', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          <div id="content">Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');

      // Should not throw error
      await user.click(chip);

      await waitFor(() => {
        expect(screen.getByTestId('content')).toBeVisible();
      });
    });

    it('should handle empty children', async () => {
      render(
        <ChipPopper icon={<Info />} label="Test">
          {null}
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      // Should not throw error
      await waitFor(() => {
        const paper = document.querySelector('.MuiPaper-root');
        expect(paper).toBeInTheDocument();
      });
    });

    it('should handle array sx props in chip slotProps', () => {
      const { container } = render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            chip: {
              sx: [{ backgroundColor: 'red' }, { color: 'white !important' }]
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = container.querySelector('.MuiChip-root');
      expect(window.getComputedStyle(chip).getPropertyValue('color')).toBe('rgb(255, 255, 255)');
      expect(window.getComputedStyle(chip).getPropertyValue('background-color')).toBe('rgb(255, 0, 0)');
    });

    it('should handle array sx props in paper slotProps', async () => {
      const { container } = render(
        <ChipPopper
          icon={<Info />}
          label="Test"
          slotProps={{
            paper: {
              sx: [{ backgroundColor: 'blue !important' }, { padding: '20px' }]
            }
          }}
        >
          <div>Content</div>
        </ChipPopper>
      );

      const chip = screen.getByText('Test').closest('.MuiChip-root');
      await user.click(chip);

      await waitFor(() => {
        const paper = container.querySelector('.MuiPaper-root');
        expect(paper).toHaveStyle({ backgroundColor: 'blue !important', padding: '20px' });
      });
    });
  });
});

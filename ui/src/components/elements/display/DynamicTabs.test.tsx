/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DynamicTabs from './DynamicTabs';

describe('DynamicTabs', () => {
  const tabs = [
    { title: 'Tab One', children: <div>Content One</div> },
    { title: 'Tab Two', children: <div>Content Two</div> },
    { title: 'Tab Three', children: <div>Content Three</div> }
  ];

  describe('rendering', () => {
    it('renders all tab labels', () => {
      render(<DynamicTabs tabs={tabs} />);
      expect(screen.getByText('Tab One')).toBeInTheDocument();
      expect(screen.getByText('Tab Two')).toBeInTheDocument();
      expect(screen.getByText('Tab Three')).toBeInTheDocument();
    });

    it('renders the first tab content by default', () => {
      render(<DynamicTabs tabs={tabs} />);
      expect(screen.getByText('Content One')).toBeInTheDocument();
    });

    it('hides non-active tab panels', () => {
      render(<DynamicTabs tabs={tabs} />);
      expect(screen.queryByText('Content Two')).not.toBeInTheDocument();
      expect(screen.queryByText('Content Three')).not.toBeInTheDocument();
    });

    it('renders a tablist with accessible aria-label', () => {
      render(<DynamicTabs tabs={tabs} />);
      expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'dynamic tabs');
    });

    it('renders correct number of tab elements', () => {
      render(<DynamicTabs tabs={tabs} />);
      expect(screen.getAllByRole('tab')).toHaveLength(3);
    });
  });

  describe('interaction', () => {
    it('switches to the second tab on click', async () => {
      const user = userEvent.setup();
      render(<DynamicTabs tabs={tabs} />);

      await user.click(screen.getByText('Tab Two'));

      expect(screen.getByText('Content Two')).toBeInTheDocument();
      expect(screen.queryByText('Content One')).not.toBeInTheDocument();
    });

    it('switches to the third tab on click', async () => {
      const user = userEvent.setup();
      render(<DynamicTabs tabs={tabs} />);

      await user.click(screen.getByText('Tab Three'));

      expect(screen.getByText('Content Three')).toBeInTheDocument();
      expect(screen.queryByText('Content One')).not.toBeInTheDocument();
    });

    it('can switch back to the first tab after clicking another', async () => {
      const user = userEvent.setup();
      render(<DynamicTabs tabs={tabs} />);

      await user.click(screen.getByText('Tab Two'));
      await user.click(screen.getByText('Tab One'));

      expect(screen.getByText('Content One')).toBeInTheDocument();
      expect(screen.queryByText('Content Two')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('assigns correct aria-controls to tabs', () => {
      render(<DynamicTabs tabs={tabs} />);
      const tabElements = screen.getAllByRole('tab');
      expect(tabElements[0]).toHaveAttribute('aria-controls', 'tabpanel-0');
      expect(tabElements[1]).toHaveAttribute('aria-controls', 'tabpanel-1');
      expect(tabElements[2]).toHaveAttribute('aria-controls', 'tabpanel-2');
    });

    it('assigns correct ids to tabs', () => {
      render(<DynamicTabs tabs={tabs} />);
      const tabElements = screen.getAllByRole('tab');
      expect(tabElements[0]).toHaveAttribute('id', 'tab-0');
      expect(tabElements[1]).toHaveAttribute('id', 'tab-1');
      expect(tabElements[2]).toHaveAttribute('id', 'tab-2');
    });

    it('renders tabpanels with correct aria-labelledby', () => {
      render(<DynamicTabs tabs={tabs} />);
      const panel = screen.getByRole('tabpanel');
      expect(panel).toHaveAttribute('aria-labelledby', 'tab-0');
    });
  });

  describe('edge cases', () => {
    it('renders with a single tab', () => {
      render(<DynamicTabs tabs={[{ title: 'Only Tab', children: <div>Only Content</div> }]} />);
      expect(screen.getByText('Only Tab')).toBeInTheDocument();
      expect(screen.getByText('Only Content')).toBeInTheDocument();
    });

    it('renders with empty tabs array', () => {
      const { container } = render(<DynamicTabs tabs={[]} />);
      expect(container.firstChild).toBeInTheDocument();
    });
  });
});

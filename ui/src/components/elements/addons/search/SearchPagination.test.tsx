/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SearchPagination from './SearchPagination';

describe('SearchPagination', () => {
  const defaultProps = {
    limit: 25,
    offset: 0,
    total: 100,
    onChange: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders pagination when total exceeds limit', () => {
      render(<SearchPagination {...defaultProps} />);
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    it('does not render when total is less than limit', () => {
      const { container } = render(<SearchPagination {...defaultProps} total={20} />);
      expect(container).toBeEmptyDOMElement();
    });

    it('does not render when total equals limit', () => {
      const { container } = render(<SearchPagination {...defaultProps} total={25} />);
      expect(container).toBeEmptyDOMElement();
    });

    it('calculates correct page count', () => {
      render(<SearchPagination {...defaultProps} total={100} limit={25} />);
      // 100/25 = 4 pages
      // MUI Pagination renders prev, page buttons, next
      expect(screen.getByText('4')).toBeInTheDocument();
    });

    it('calculates correct page count with non-even division', () => {
      render(<SearchPagination {...defaultProps} total={101} limit={25} />);
      // ceil(101/25) = 5 pages
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('highlights the current page based on offset', () => {
      render(<SearchPagination {...defaultProps} offset={50} />);
      // offset 50 with limit 25 = page 3
      const page3 = screen.getByText('3');
      expect(page3.closest('button')).toHaveAttribute('aria-current', 'true');
    });
  });

  describe('interaction', () => {
    it('calls onChange with correct offset when clicking page 2', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<SearchPagination {...defaultProps} onChange={onChange} />);

      await user.click(screen.getByText('2'));
      expect(onChange).toHaveBeenCalledWith(25);
    });

    it('calls onChange with correct offset when clicking page 3', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<SearchPagination {...defaultProps} onChange={onChange} />);

      await user.click(screen.getByText('3'));
      expect(onChange).toHaveBeenCalledWith(50);
    });

    it('calls onChange with 0 when clicking page 1', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<SearchPagination {...defaultProps} offset={25} onChange={onChange} />);

      await user.click(screen.getByText('1'));
      expect(onChange).toHaveBeenCalledWith(0);
    });
  });

  describe('edge cases', () => {
    it('does not render when limit is 0', () => {
      const { container } = render(<SearchPagination {...defaultProps} limit={0} />);
      expect(container).toBeEmptyDOMElement();
    });

    it('does not render when total is 0', () => {
      const { container } = render(<SearchPagination {...defaultProps} total={0} />);
      expect(container).toBeEmptyDOMElement();
    });
  });
});

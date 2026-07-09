import { createContext, useContext } from 'react';

vi.mock('use-context-selector', async () => {
  const actual = await vi.importActual('use-context-selector');
  return {
    ...actual,
    createContext,
    useContextSelector: (_context: any, selector: any) => selector(useContext(_context))
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import { render, screen, waitFor } from '@testing-library/react';
import { ParameterContext, type ParameterContextType } from 'components/app/providers/ParameterProvider';
import dayjs from 'dayjs';
import minMax from 'dayjs/plugin/minMax';
import { type PropsWithChildren } from 'react';

dayjs.extend(minMax);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Import after mocks
import CustomSpan from './CustomSpan';

const mockSetCustomSpan = vi.fn();

const defaultCtx: Partial<ParameterContextType> = {
  span: 'date.range.custom',
  startDate: undefined,
  endDate: undefined,
  setCustomSpan: mockSetCustomSpan
};

const makeWrapper =
  (ctx: Partial<ParameterContextType>) =>
  ({ children }: PropsWithChildren) => {
    return (
      <ParameterContext.Provider value={{ ...defaultCtx, ...ctx } as ParameterContextType}>
        {children}
      </ParameterContext.Provider>
    );
  };

describe('CustomSpan', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useEffect – date initialisation', () => {
    it('should set both dates to defaults when both are null', async () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.custom', startDate: undefined, endDate: undefined })
      });

      await waitFor(() => expect(mockSetCustomSpan).toHaveBeenCalledOnce());

      const [start, end] = mockSetCustomSpan.mock.calls[0];
      const startDate = dayjs(start);
      const endDate = dayjs(end);

      expect(startDate.isBefore(endDate)).toBe(true);
      expect(dayjs().diff(startDate, 'hour')).toBeGreaterThanOrEqual(47);
      expect(dayjs().diff(startDate, 'hour')).toBeLessThanOrEqual(49);
      expect(dayjs().diff(endDate, 'hour')).toBeGreaterThanOrEqual(23);
      expect(dayjs().diff(endDate, 'hour')).toBeLessThanOrEqual(25);
    });

    it('should set default start date when only endDate is provided', async () => {
      // Use a recent end date that's after the default start (now - 2 days)
      const existingEnd = dayjs().subtract(1, 'hour').toISOString();

      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.custom', startDate: undefined, endDate: existingEnd })
      });

      await waitFor(() => expect(mockSetCustomSpan).toHaveBeenCalledOnce());

      const [start, end] = mockSetCustomSpan.mock.calls[0];
      expect(end).toBe(existingEnd);
      expect(dayjs(start).isBefore(dayjs(end))).toBe(true);
    });

    it('should set default end date when only startDate is provided', async () => {
      // Use a recent start date that's before the default end (now - 1 day)
      const existingStart = dayjs().subtract(3, 'day').toISOString();

      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.custom', startDate: existingStart, endDate: undefined })
      });

      await waitFor(() => expect(mockSetCustomSpan).toHaveBeenCalledOnce());

      const [start, end] = mockSetCustomSpan.mock.calls[0];
      expect(start).toBe(existingStart);
      expect(dayjs(end).isAfter(dayjs(start))).toBe(true);
    });

    it('should NOT call setCustomSpan when both dates are already set', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({
          span: 'date.range.custom',
          startDate: dayjs().subtract(3, 'day').toISOString(),
          endDate: dayjs().subtract(1, 'hour').toISOString()
        })
      });

      expect(mockSetCustomSpan).not.toHaveBeenCalled();
    });

    it('should NOT call setCustomSpan when span is not custom', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.1.month', startDate: undefined, endDate: undefined })
      });

      expect(mockSetCustomSpan).not.toHaveBeenCalled();
    });

    it('should NOT call setCustomSpan when span is undefined', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: undefined, startDate: undefined, endDate: undefined })
      });

      expect(mockSetCustomSpan).not.toHaveBeenCalled();
    });

    it('should ensure startDate is before endDate even if existing startDate is after default endDate', async () => {
      const futureStart = dayjs().add(1, 'hour').toISOString();

      render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.custom', startDate: futureStart, endDate: undefined })
      });

      await waitFor(() => expect(mockSetCustomSpan).toHaveBeenCalledOnce());

      const [start, end] = mockSetCustomSpan.mock.calls[0];
      expect(dayjs(start).isBefore(dayjs(end))).toBe(true);
    });
  });

  describe('rendering', () => {
    it('should render nothing when span is not custom', () => {
      const { container } = render(<CustomSpan />, {
        wrapper: makeWrapper({ span: 'date.range.1.month' })
      });

      expect(container.innerHTML).toBe('');
    });

    it('should render nothing when span is undefined', () => {
      const { container } = render(<CustomSpan />, {
        wrapper: makeWrapper({ span: undefined })
      });

      expect(container.innerHTML).toBe('');
    });

    it('should render two date pickers when span is custom', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({
          span: 'date.range.custom',
          startDate: dayjs().subtract(3, 'day').toISOString(),
          endDate: dayjs().subtract(1, 'hour').toISOString()
        })
      });

      expect(screen.getByLabelText('date.select.start')).toBeInTheDocument();
      expect(screen.getByLabelText('date.select.end')).toBeInTheDocument();
    });

    it('should render pickers for any span ending with "custom"', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({
          span: 'my.prefix.custom',
          startDate: dayjs().subtract(3, 'day').toISOString(),
          endDate: dayjs().subtract(1, 'hour').toISOString()
        })
      });

      expect(screen.getByLabelText('date.select.start')).toBeInTheDocument();
      expect(screen.getByLabelText('date.select.end')).toBeInTheDocument();
    });
  });

  describe('onChange handlers', () => {
    it('should not call setCustomSpan when both dates are present on render', () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({
          span: 'date.range.custom',
          startDate: dayjs().subtract(3, 'day').toISOString(),
          endDate: dayjs().subtract(1, 'hour').toISOString()
        })
      });

      const startPicker = screen.getByLabelText('date.select.start');
      expect(startPicker).toBeInTheDocument();

      expect(mockSetCustomSpan).not.toHaveBeenCalled();
    });

    it('should render start picker with fallback value when startDate is null', async () => {
      render(<CustomSpan />, {
        wrapper: makeWrapper({
          span: 'date.range.custom',
          startDate: undefined,
          endDate: dayjs().subtract(1, 'hour').toISOString()
        })
      });

      // When startDate is null, the picker's value falls back to dayjs().subtract(1, 'days')
      const startInput = screen.getByLabelText('date.select.start');
      expect(startInput).toBeInTheDocument();
      // The input should have a value (the fallback), not be empty
      expect((startInput as HTMLInputElement).value).not.toBe('');
    });
  });
});

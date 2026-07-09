import { render, screen } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { ModalContext } from 'components/app/providers/ModalProvider';
import i18n from 'i18n';
import { I18nextProvider } from 'react-i18next';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TemplateCard from './TemplateCard';

const mockShowModal = vi.fn();

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nextProvider i18n={i18n as any}>
    <ModalContext.Provider value={{ showModal: mockShowModal } as any}>{children}</ModalContext.Provider>
  </I18nextProvider>
);

describe('TemplateCard', () => {
  let user: UserEvent;

  beforeEach(() => {
    user = userEvent.setup();
    vi.clearAllMocks();
  });

  it('should render template analytic and detection', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: 'Test Detection',
      type: 'personal' as const,
      keys: ['howler.detection', 'event.id']
    };

    render(<TemplateCard template={template as any} />, { wrapper: Wrapper });

    expect(screen.getByText(/Test Analytic/)).toBeInTheDocument();
    expect(screen.getByText(/Test Detection/)).toBeInTheDocument();
  });

  it('should render template keys', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: 'Test Detection',
      type: 'personal' as const,
      keys: ['howler.detection', 'event.id']
    };

    render(<TemplateCard template={template as any} />, { wrapper: Wrapper });

    expect(screen.getByText('howler.detection')).toBeInTheDocument();
    expect(screen.getByText('event.id')).toBeInTheDocument();
  });

  it('should render personal type icon with tooltip', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'personal' as const,
      keys: ['howler.detection']
    };

    render(<TemplateCard template={template as any} />, { wrapper: Wrapper });

    // The personal icon (Person) should be rendered
    expect(document.querySelector('[data-testid="PersonIcon"]')).toBeInTheDocument();
  });

  it('should render global type icon', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'global' as const,
      keys: ['howler.detection']
    };

    render(<TemplateCard template={template as any} />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="LanguageIcon"]')).toBeInTheDocument();
  });

  it('should render readonly type icon', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'readonly' as const,
      keys: ['howler.detection']
    };

    render(<TemplateCard template={template as any} />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="LockIcon"]')).toBeInTheDocument();
  });

  it('should not show error button when error is false', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'personal' as const,
      keys: ['howler.detection']
    };

    render(<TemplateCard template={template as any} error={false} />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="ReportProblemIcon"]')).not.toBeInTheDocument();
  });

  it('should show error button and trigger modal when error is true', async () => {
    const mockOnRemove = vi.fn();
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'personal' as const,
      keys: ['howler.detection']
    };

    render(<TemplateCard template={template as any} error onRemove={mockOnRemove} />, { wrapper: Wrapper });

    expect(document.querySelector('[data-testid="ReportProblemIcon"]')).toBeInTheDocument();

    const errorButton = screen.getByText('Invalid Detection');
    await user.click(errorButton);

    expect(mockShowModal).toHaveBeenCalled();
  });

  it('should apply custom className', () => {
    const template = {
      template_id: 'tmpl-1',
      analytic: 'Test Analytic',
      detection: null,
      type: 'personal' as const,
      keys: ['howler.detection']
    };

    const { container } = render(<TemplateCard template={template as any} className="custom-class" />, {
      wrapper: Wrapper
    });

    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });
});

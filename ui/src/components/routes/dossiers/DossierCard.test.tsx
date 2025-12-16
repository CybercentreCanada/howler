/* eslint-disable react/jsx-no-literals */
/* eslint-disable import/imports-first */
/// <reference types="vitest" />
import { render, screen, waitFor } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import { AvatarContext } from 'components/app/providers/AvatarProvider';
import i18n from 'i18n';
import { act } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createMockDossier } from 'tests/utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DossierCard from './DossierCard';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockAvatarContext = {
  getAvatar: vi.fn(userId => Promise.resolve('https://images.example.com/' + userId))
};

// Test wrapper
const Wrapper = ({ children }: { children: React.ReactNode }) => {
  return (
    <I18nextProvider i18n={i18n as any}>
      <AvatarContext.Provider value={mockAvatarContext as any}>{children}</AvatarContext.Provider>
    </I18nextProvider>
  );
};

describe('DossierCard', () => {
  let user: UserEvent;
  let mockOnDelete: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    user = userEvent.setup();
    mockOnDelete = vi.fn();
    vi.clearAllMocks();
  });

  describe('Rendering Conditions', () => {
    it('should render with required props only', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('Test Dossier')).toBeInTheDocument();
      });
    });

    it('should render with all props', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} className="custom-class" onDelete={mockOnDelete} />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        expect(screen.getByText('Test Dossier')).toBeInTheDocument();
      });
    });

    it('should apply custom className when provided', async () => {
      const dossier = createMockDossier();

      const { container } = render(<DossierCard dossier={dossier} className="custom-class" />, { wrapper: Wrapper });

      await waitFor(() => {
        const card = container.querySelector('.custom-class');
        expect(card).toBeInTheDocument();
      });
    });

    it('should render without className when not provided', async () => {
      const dossier = createMockDossier();

      const { container } = render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(container.querySelector('.MuiCard-root')).toBeInTheDocument();
      });
    });
  });

  describe('UI Element Display', () => {
    it('should display dossier title', async () => {
      const dossier = createMockDossier({ title: 'My Custom Dossier' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('My Custom Dossier')).toBeInTheDocument();
      });
    });

    it('should display dossier query in code block', async () => {
      const dossier = createMockDossier({ query: 'howler.id:*' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        const codeElement = screen.getByText('howler.id:*');
        expect(codeElement).toBeInTheDocument();
        expect(codeElement.tagName).toBe('CODE');
      });
    });

    it('should display Person icon for personal dossier type', async () => {
      const dossier = createMockDossier({ type: 'personal' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        // Check for Person icon via MUI's data-testid or by checking the tooltip
        const tooltip = screen.getByLabelText(/personal/i);
        expect(tooltip).toBeInTheDocument();
      });
    });

    it('should display Language icon for global dossier type', async () => {
      const dossier = createMockDossier({ type: 'global' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        // Check for Language icon via tooltip
        const tooltip = screen.getByLabelText(/global/i);
        expect(tooltip).toBeInTheDocument();
      });
    });

    it('should display HowlerAvatar with correct userId', async () => {
      const dossier = createMockDossier({ owner: 'john.doe' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText('john.doe')).toBeInTheDocument();
      });
    });

    it('should display delete button when onDelete is provided', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        const deleteButton = screen.getByRole('button');
        expect(deleteButton).toBeInTheDocument();
      });
    });

    it('should not display delete button when onDelete is not provided', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
      });
    });

    it('should have tooltip on type icon', async () => {
      const dossier = createMockDossier({ type: 'personal' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/personal/i)).toBeInTheDocument();
      });
    });

    it('should have tooltip on delete button', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/delete/i)).toBeInTheDocument();
      });
    });
  });

  describe('Button States & Interactions', () => {
    it('should call onDelete with correct parameters when delete button is clicked', async () => {
      const dossier = createMockDossier({ dossier_id: 'my-dossier-123' });

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(mockOnDelete).toHaveBeenCalledTimes(1);
        expect(mockOnDelete).toHaveBeenCalledWith(expect.any(Object), 'my-dossier-123');
      });
    });

    it('should call onDelete with event object', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button');
      await user.click(deleteButton);

      await waitFor(() => {
        const eventArg = mockOnDelete.mock.calls[0][0];
        expect(eventArg).toBeDefined();
        expect(eventArg.type).toBe('click');
      });
    });

    it('should not crash when delete button is clicked multiple times', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button');
      await user.click(deleteButton);
      await user.click(deleteButton);
      await user.click(deleteButton);

      await waitFor(() => {
        expect(mockOnDelete).toHaveBeenCalledTimes(3);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty title', async () => {
      const dossier = createMockDossier({ title: '' });

      const { container } = render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(container).toBeInTheDocument();
      });
    });

    it('should handle empty query', async () => {
      const dossier = createMockDossier({ query: '' });

      const { container } = render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        const codeElement = container.querySelector('code');
        expect(codeElement).toBeEmptyDOMElement();
      });
    });

    it('should handle very long title', async () => {
      const longTitle = 'A'.repeat(200);
      const dossier = createMockDossier({ title: longTitle });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(longTitle)).toBeInTheDocument();
      });
    });

    it('should handle very long query', async () => {
      const longQuery = 'howler.id:*' + ' AND howler.status:open'.repeat(50);
      const dossier = createMockDossier({ query: longQuery });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText(longQuery)).toBeInTheDocument();
      });
    });

    it('should handle special characters in title', async () => {
      const dossier = createMockDossier({ title: '<script>alert("xss")</script>' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('<script>alert("xss")</script>')).toBeInTheDocument();
      });
    });

    it('should handle special characters in query', async () => {
      const dossier = createMockDossier({ query: 'howler.id:*&query=<test>' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByText('howler.id:*&query=<test>')).toBeInTheDocument();
      });
    });

    it('should handle undefined owner', async () => {
      const dossier = createMockDossier({ owner: undefined as any });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText('Unknown')).toBeInTheDocument();
      });
    });

    it('should handle null owner', async () => {
      const dossier = createMockDossier({ owner: null as any });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText('Unknown')).toBeInTheDocument();
      });
    });
  });

  describe('Dossier Types', () => {
    it('should render correctly for personal type', async () => {
      const dossier = createMockDossier({ type: 'personal' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/personal/i)).toBeInTheDocument();
      });
    });

    it('should render correctly for global type', async () => {
      const dossier = createMockDossier({ type: 'global' });

      render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByLabelText(/global/i)).toBeInTheDocument();
      });
    });

    it('should handle switching between types', async () => {
      const { rerender } = render(<DossierCard dossier={createMockDossier({ type: 'personal' })} />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        expect(screen.getByLabelText(/personal/i)).toBeInTheDocument();
      });

      rerender(<DossierCard dossier={createMockDossier({ type: 'global' })} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/global/i)).toBeInTheDocument();
      });
    });
  });

  describe('Integration Tests', () => {
    it('should render complete card with all elements', async () => {
      const dossier = createMockDossier({
        dossier_id: 'full-test',
        title: 'Complete Dossier',
        query: 'howler.status:open AND howler.assigned:me',
        type: 'personal',
        owner: 'admin'
      });

      render(<DossierCard dossier={dossier} className="test-class" onDelete={mockOnDelete} />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        // Check all elements are present
        expect(screen.getByText('Complete Dossier')).toBeInTheDocument();
        expect(screen.getByText('howler.status:open AND howler.assigned:me')).toBeInTheDocument();
        expect(screen.getByLabelText(/personal/i)).toBeInTheDocument();
        expect(screen.getByLabelText('admin')).toBeInTheDocument();
        expect(screen.getByRole('button')).toBeInTheDocument();
      });
    });

    it('should handle multiple dossier cards with different data', async () => {
      const dossiers = [
        createMockDossier({ dossier_id: 'dossier-1', title: 'Dossier 1', type: 'personal' }),
        createMockDossier({ dossier_id: 'dossier-2', title: 'Dossier 2', type: 'global' }),
        createMockDossier({ dossier_id: 'dossier-3', title: 'Dossier 3', type: 'personal' })
      ];

      render(
        <Wrapper>
          {dossiers.map(dossier => (
            <DossierCard key={dossier.dossier_id} dossier={dossier} onDelete={mockOnDelete} />
          ))}
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Dossier 1')).toBeInTheDocument();
        expect(screen.getByText('Dossier 2')).toBeInTheDocument();
        expect(screen.getByText('Dossier 3')).toBeInTheDocument();
        expect(screen.getAllByRole('button')).toHaveLength(3);
      });
    });

    it('should work with different owners', async () => {
      const owners = ['user1', 'user2', 'admin'];
      const { rerender } = render(<DossierCard dossier={createMockDossier({ owner: owners[0] })} />, {
        wrapper: Wrapper
      });

      for (const owner of owners) {
        rerender(<DossierCard dossier={createMockDossier({ owner })} />);
        await waitFor(() => {
          expect(screen.getByLabelText(owner)).toBeInTheDocument();
        });
      }
    });
  });

  describe('Accessibility', () => {
    it('should have accessible delete button', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        const deleteButton = screen.getByRole('button');
        expect(deleteButton).toBeInTheDocument();
        expect(deleteButton).toHaveAccessibleName();
      });
    });

    it('should have tooltips for icons', async () => {
      const dossier = createMockDossier({ type: 'personal' });

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        // Type icon tooltip
        expect(screen.getByLabelText(/personal/i)).toBeInTheDocument();

        // Delete button tooltip
        expect(screen.getByLabelText(/delete/i)).toBeInTheDocument();
      });
    });

    it('should have proper semantic HTML structure', async () => {
      const dossier = createMockDossier();

      const { container } = render(<DossierCard dossier={dossier} />, { wrapper: Wrapper });

      await waitFor(() => {
        // Should have a card
        expect(container.querySelector('.MuiCard-root')).toBeInTheDocument();

        // Should have code element for query
        expect(container.querySelector('code')).toBeInTheDocument();
      });
    });

    it('should maintain focus on delete button', async () => {
      const dossier = createMockDossier();

      render(<DossierCard dossier={dossier} onDelete={mockOnDelete} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button');
      act(() => {
        deleteButton.focus();
      });

      await waitFor(() => {
        expect(deleteButton).toHaveFocus();
      });
    });
  });

  describe('Prop Changes', () => {
    it('should update when dossier prop changes', async () => {
      const { rerender } = render(<DossierCard dossier={createMockDossier({ title: 'Original' })} />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        expect(screen.getByText('Original')).toBeInTheDocument();
      });

      rerender(<DossierCard dossier={createMockDossier({ title: 'Updated' })} />);

      await waitFor(() => {
        expect(screen.getByText('Updated')).toBeInTheDocument();
        expect(screen.queryByText('Original')).not.toBeInTheDocument();
      });
    });

    it('should update when onDelete prop is added', async () => {
      const { rerender } = render(<DossierCard dossier={createMockDossier()} />, { wrapper: Wrapper });

      await waitFor(() => {
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
      });

      rerender(<DossierCard dossier={createMockDossier()} onDelete={mockOnDelete} />);

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });
    });

    it('should update when onDelete prop is removed', async () => {
      const { rerender } = render(<DossierCard dossier={createMockDossier()} onDelete={mockOnDelete} />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        expect(screen.getByRole('button')).toBeInTheDocument();
      });

      rerender(<DossierCard dossier={createMockDossier()} />);

      await waitFor(() => {
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
      });
    });

    it('should update when className changes', async () => {
      const { container, rerender } = render(<DossierCard dossier={createMockDossier()} className="class-1" />, {
        wrapper: Wrapper
      });

      await waitFor(() => {
        expect(container.querySelector('.class-1')).toBeInTheDocument();
      });

      rerender(<DossierCard dossier={createMockDossier()} className="class-2" />);

      await waitFor(() => {
        expect(container.querySelector('.class-2')).toBeInTheDocument();
        expect(container.querySelector('.class-1')).not.toBeInTheDocument();
      });
    });
  });
});

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SettingsSection from './SettingsSection';

describe('SettingsSection', () => {
  it('should render the title in a table header', () => {
    render(
      <SettingsSection title="Test Section" colSpan={3}>
        <tr>
          <td>Content</td>
        </tr>
      </SettingsSection>
    );

    expect(screen.getByText('Test Section')).toBeInTheDocument();
  });

  it('should render children inside a table body', () => {
    render(
      <SettingsSection title="Test Section" colSpan={2}>
        <tr>
          <td>Row Content</td>
        </tr>
      </SettingsSection>
    );

    expect(screen.getByText('Row Content')).toBeInTheDocument();
  });

  it('should use the title as the table aria-label', () => {
    render(
      <SettingsSection title="Accessible Section" colSpan={3}>
        <tr>
          <td>Content</td>
        </tr>
      </SettingsSection>
    );

    expect(screen.getByRole('table', { name: 'Accessible Section' })).toBeInTheDocument();
  });
});

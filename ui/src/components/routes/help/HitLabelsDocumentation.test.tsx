/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => `${key} - description` })
}));

import HitLabelsDocumentation from './HitLabelsDocumentation';

describe('HitLabelsDocumentation', () => {
  it('renders label rows and translated descriptions for the configured label types', () => {
    render(<HitLabelsDocumentation />);

    expect(screen.getByText('help.hit.labels.title - description')).toBeInTheDocument();
    expect(screen.getByText('Insight')).toBeInTheDocument();
    expect(screen.getAllByText('description').length).toBeGreaterThan(0);
    expect(screen.getByText('threat')).toBeInTheDocument();
  });
});

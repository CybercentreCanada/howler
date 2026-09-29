/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('components/elements/display/HowlerCard', () => ({
  default: ({ children }: any) => <div>{children}</div>
}));

vi.mock('components/elements/display/json/JSONViewer', () => ({
  default: ({ data }: any) => <div>json:{data.howler.id}</div>
}));

vi.mock('components/elements/hit/HitBanner', () => ({
  default: ({ hit, layout }: any) => (
    <div>
      banner:{hit.howler.id}:{layout}
    </div>
  )
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key })
}));

import HitBannerDocumentation from './HitBannerDocumentation';

describe('HitBannerDocumentation', () => {
  it('renders the sample hit banner and JSON viewer', () => {
    render(<HitBannerDocumentation />);

    expect(screen.getByText('help.hit.banner.title')).toBeInTheDocument();
    expect(screen.getByText(/banner:howler.id/)).toBeInTheDocument();
    expect(screen.getByText('json:howler.id')).toBeInTheDocument();
  });
});

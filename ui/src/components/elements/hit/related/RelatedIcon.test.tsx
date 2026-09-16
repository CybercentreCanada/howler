import { render, screen } from '@testing-library/react';
import type { ApiType } from 'models/entities/generated/ApiType';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RelatedIcon from './RelatedIcon';

const theme = vi.hoisted(() => ({ isDark: false }));

vi.mock('@iconify/react', () => ({
  Icon: ({ icon, fontSize }: { icon: string; fontSize?: string }) => (
    <span id="icon" data-icon={icon} data-font-size={fontSize} />
  )
}));

vi.mock('@tui/core', () => ({
  useAppTheme: () => theme
}));

const renderWithConfig = (children: ReactNode, config: Partial<ApiType> = {}) => {
  return render(
    <ApiConfigContext.Provider value={{ config, setConfig: vi.fn(), loaded: true }}>
      {children}
    </ApiConfigContext.Provider>
  );
};

describe('RelatedIcon', () => {
  beforeEach(() => {
    theme.isDark = false;
  });

  it('renders nothing when no icon is provided', () => {
    const { container } = renderWithConfig(<RelatedIcon title="Example" />);

    expect(container).toBeEmptyDOMElement();
  });

  it('renders a configured application image case-insensitively', () => {
    renderWithConfig(<RelatedIcon icon="cLuE" title="Clue" />, {
      configuration: {
        ui: {
          apps: [
            {
              name: 'Clue',
              img_l: 'https://example.test/clue-light.png',
              img_d: 'https://example.test/clue-dark.png',
              alt: 'Clue',
              route: '/clue',
              classification: 'U'
            }
          ]
        }
      }
    } as Partial<ApiType>);

    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/clue-light.png');
    expect(screen.getByRole('img')).toHaveAttribute('alt', 'Clue');
  });

  it('uses the dark configured application image when the app theme is dark', () => {
    theme.isDark = true;

    renderWithConfig(<RelatedIcon icon="Clue" title="Clue" />, {
      configuration: {
        ui: {
          apps: [
            {
              name: 'Clue',
              img_l: 'https://example.test/clue-light.png',
              img_d: 'https://example.test/clue-dark.png',
              alt: 'Clue',
              route: '/clue',
              classification: 'U'
            }
          ]
        }
      }
    } as Partial<ApiType>);

    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.test/clue-dark.png');
  });

  it('renders a direct HTTP icon as an avatar image', () => {
    renderWithConfig(<RelatedIcon icon="http://example.test/icon.svg" href="https://example.test" />);

    expect(screen.getByRole('img')).toHaveAttribute('src', 'http://example.test/icon.svg');
    expect(screen.getByRole('img')).toHaveAttribute('alt', 'https://example.test');
  });

  it('uses the title as the image alt text when no href is provided', () => {
    renderWithConfig(<RelatedIcon icon="https://example.test/icon.svg" title="Example" compact />);

    expect(screen.getByRole('img')).toHaveAttribute('alt', 'Example');
    expect(screen.getByRole('img').parentElement).toHaveStyle({ width: '32px', height: '32px' });
  });

  it('renders an Iconify icon when no image can be resolved', () => {
    renderWithConfig(<RelatedIcon icon="mdi:link-variant" />);

    expect(screen.getByTestId('icon')).toHaveAttribute('data-icon', 'mdi:link-variant');
    expect(screen.getByTestId('icon')).toHaveAttribute('data-font-size', '1.5rem');
  });
});

import type { LeftNavMenuProps } from '@tui/core';
import {
  AccountTreeOutlined,
  Book,
  DynamicForm,
  ErrorOutline,
  LanguageOutlined,
  PaletteOutlined,
  Security,
  ViewQuiltOutlined,
  WidgetsOutlined
} from '@mui/icons-material';
import Divider from '@mui/material/Divider';
import { useMemo } from 'react';

export const useMyLeftNav = (): LeftNavMenuProps[] => {
  // Example routes are intentionally grouped.
  // Feel free to remove this section entirely once onboarding is complete.
  const mainMenu: LeftNavMenuProps = useMemo(
    () => ({
      id: 'menu1',
      type: 'menu',
      items: [
        {
          id: 'examples.overview',
          type: 'route',
          label: 'Overview',
          i18nKey: 'menu.examples.overview',
          tooltipI18nKey: 'menu.examples.overview.tooltip',
          icon: <LanguageOutlined />,
          route: '/examples'
        },
        {
          id: 'examples.layout',
          type: 'route',
          label: 'Layout',
          i18nKey: 'menu.examples.layout',
          tooltipI18nKey: 'menu.examples.layout.tooltip',
          icon: <ViewQuiltOutlined />,
          route: '/examples/layout'
        },
        {
          id: 'examples.routing',
          type: 'menu',
          label: 'Routing',
          i18nKey: 'menu.examples.routing',
          tooltipI18nKey: 'menu.examples.routing.tooltip',
          icon: <AccountTreeOutlined />,
          route: '/examples/routing',
          items: [
            {
              id: 'examples.routing.overview',
              type: 'route',
              i18nKey: 'menu.examples.routing.overview',
              tooltipI18nKey: 'menu.examples.routing.overview.tooltip',
              route: '/examples/routing',
              target: '_blank'
            },
            {
              id: 'examples.routing.basic',
              type: 'route',
              i18nKey: 'menu.examples.routing.basic',
              tooltipI18nKey: 'menu.examples.routing.basic.tooltip',
              route: '/examples/routing/basic',
              icon: <Book />
            },
            {
              id: 'examples.routing.nested',
              type: 'route',
              i18nKey: 'menu.examples.routing.nested',
              tooltipI18nKey: 'menu.examples.routing.nested.tooltip',
              route: '/examples/routing/nested',
              matcher: RegExp('^/examples/routing/nested(/.+)?$'),
              icon: <WidgetsOutlined />
            },
            {
              id: 'examples.routing.dynamic',
              type: 'route',
              i18nKey: 'menu.examples.routing.dynamic',
              tooltipI18nKey: 'menu.examples.routing.dynamic.tooltip',
              route: '/examples/routing/dynamic',
              matcher: RegExp('^/examples/routing/dynamic(/.+)?$'),
              icon: <DynamicForm />
            },
            {
              id: 'examples.routing.error',
              type: 'route',
              i18nKey: 'menu.examples.routing.error',
              tooltipI18nKey: 'menu.examples.routing.error.tooltip',
              route: '/examples/routing/error',
              icon: <ErrorOutline />
            }
          ]
        },
        {
          id: 'examples.themes',
          type: 'route',
          i18nKey: 'menu.examples.themes',
          tooltipI18nKey: 'menu.examples.themes.tooltip',
          icon: <PaletteOutlined />,
          route: '/examples/themes'
        },
        { id: 'drawer.divider.2', type: 'slot', component: Divider }
      ]
    }),
    []
  );

  // Main routes are intentionally grouped.
  // Feel free to remove this section entirely once onboarding is complete.
  const classificationMenu: LeftNavMenuProps = useMemo(
    () => ({
      id: 'menu2',
      type: 'menu',
      items: [
        {
          id: 'examples.classifications',
          type: 'menu',
          label: 'Classifications',
          i18nKey: 'menu.examples.classifications',
          tooltipI18nKey: 'menu.examples.classifications.tooltip',
          icon: <Security />,
          route: '/examples/classifications',
          items: [
            {
              id: 'examples.classifications.overview',
              type: 'route',
              i18nKey: 'menu.examples.classifications.overview',
              tooltipI18nKey: 'menu.examples.classifications.overview.tooltip',
              route: '/examples/classifications'
            },

            {
              id: 'examples.classifications.security',
              type: 'route',
              i18nKey: 'menu.examples.classifications.security',
              tooltipI18nKey: 'menu.examples.classifications.security.tooltip',
              route: '/examples/classifications/security'
            },
            {
              id: 'examples.classifications.tlp',
              type: 'route',
              i18nKey: 'menu.examples.classifications.tlp',
              tooltipI18nKey: 'menu.examples.classifications.tlp.tooltip',
              route: '/examples/classifications/tlp'
            }
          ]
        }
      ]
    }),
    []
  );

  return useMemo(() => [mainMenu, classificationMenu], [mainMenu, classificationMenu]);
};

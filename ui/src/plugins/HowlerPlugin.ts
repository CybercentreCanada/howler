import type { HowlerHelper } from 'components/elements/display/handlebars/helpers';
import type { ActionButton } from 'components/elements/hit/actions/SharedComponents';
import type { StatusProps } from 'components/elements/hit/HitBanner';
import type { PivotLinkProps } from 'components/elements/hit/related/PivotLink';
import type { PluginChipProps } from 'components/elements/PluginChip';
import type { PluginTypographyProps } from 'components/elements/PluginTypography';
import type { CustomActionProps } from 'components/routes/action/edit/ActionEditor';
import type { LeadFormProps } from 'components/routes/dossiers/LeadEditor';
import type { PivotFormProps } from 'components/routes/dossiers/PivotForm';
import type { PluginDocumentation } from 'components/routes/help/ActionDocumentation';
import i18nInstance from 'i18n';
import type { i18n as I18N } from 'i18next';
import { difference } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type React from 'react';
import type { PropsWithChildren } from 'react';
import type { IPlugin, PluginStore } from 'react-pluggable';
import type { MainMenuInsertOperation } from './store';
import howlerPluginStore from './store';

const INTERNAL_FUNCTIONS = [
  'constructor',
  'getPluginName',
  'getDependencies',
  'init',
  'activate',
  'deactivate',
  'addLead',
  'addPivot',
  'addUserMenuItem',
  'addAdminMenuItem',
  'addRoute',
  'addSitemap',
  'addRouteAndSitemap',
  'addMainMenuItem',
  'addMainMenuDivider',
  'addOperation'
];

abstract class HowlerPlugin implements IPlugin {
  abstract name: string;
  abstract version: string;
  abstract author: string;
  abstract description: string;

  pluginStore: PluginStore;

  private functionsToRemove: string[] = [];

  getPluginName(): string {
    return `${this.name}@${this.version}`;
  }

  getDependencies(): string[] {
    return [];
  }

  init(pluginStore: PluginStore): void {
    this.pluginStore = pluginStore;
  }

  activate() {
    difference(Object.getOwnPropertyNames(HowlerPlugin.prototype), INTERNAL_FUNCTIONS).forEach(_function => {
      this.pluginStore.addFunction(`${this.name}.${_function}`, this[_function]);
      this.functionsToRemove.push(`${this.name}.${_function}`);
    });

    this.localization(i18nInstance);
  }

  deactivate() {
    difference(Object.getOwnPropertyNames(HowlerPlugin.prototype), INTERNAL_FUNCTIONS).forEach(_function =>
      this.pluginStore.removeFunction(`${this.name}.${_function}`)
    );

    this.functionsToRemove.forEach(name => this.pluginStore.removeFunction(name));
  }

  addLead(
    format: string,
    form: (props: LeadFormProps) => React.ReactNode,
    renderer: (content: string, metadata: any, hit?: Hit) => React.ReactNode
  ) {
    if (!howlerPluginStore.addLead(format)) {
      // eslint-disable-next-line no-console
      console.error(`Lead format ${format} already configured, not enabling for plugin ${this.getPluginName()}`);
      return;
    }

    this.pluginStore.addFunction(`lead.${format}`, renderer);
    this.functionsToRemove.push(`lead.${format}`);

    this.pluginStore.addFunction(`lead.${format}.form`, form);
    this.functionsToRemove.push(`lead.${format}.form`);

    // eslint-disable-next-line no-console
    console.debug(`Lead format ${format} enabled for plugin ${this.getPluginName()}`);
  }

  addPivot(
    format: string,
    form: (props: PivotFormProps) => React.ReactNode,
    renderer: (props: PivotLinkProps) => React.ReactNode
  ) {
    if (!howlerPluginStore.addPivot(format)) {
      // eslint-disable-next-line no-console
      console.error(`Pivot format ${format} already configured, not enabling for plugin ${this.getPluginName()}`);
      return;
    }

    this.pluginStore.addFunction(`pivot.${format}`, renderer);
    this.functionsToRemove.push(`pivot.${format}`);

    this.pluginStore.addFunction(`pivot.${format}.form`, form);
    this.functionsToRemove.push(`pivot.${format}.form`);

    // eslint-disable-next-line no-console
    console.debug(`Pivot format ${format} enabled for plugin ${this.getPluginName()}`);
  }

  /**
   * Adds a single menu item to the User Menu group under the Avatar Menu,
   * items are added before the 'Settings' and 'Logout' menu items.
   *
   * @param i18nKey Translation Key or Title
   * @param route Route to navigate to, '/settings' for example
   * @param icon JSX Icon element, <Settings/> for example
   */
  addUserMenuItem(i18nKey: string, route: string, icon: JSX.Element) {
    howlerPluginStore.addUserMenuItem({
      i18nKey: i18nKey,
      route: route,
      icon: icon
    });
  }

  /**
   * Adds a single menu item to the Admin Menu group under the Avatar Menu,
   * items are added to the end of the existing Admin menu items.
   *
   * @param i18nKey Translation Key or Title
   * @param route Route to navigate to, '/settings' for example
   * @param icon JSX Icon element, <Settings/> for example
   */
  addAdminMenuItem(i18nKey: string, route: string, icon: JSX.Element) {
    howlerPluginStore.addAdminMenuItem({
      i18nKey: i18nKey,
      route: route,
      icon: icon
    });
  }

  /**
   * Adds a single route to the system to load, items are added to the end of
   * base routes defined.
   *
   * @param path Route path, should not start with /
   * @param element Element the route directs to
   * @param children Child routes if required
   */
  addRoute(path: string, element: JSX.Element, children?: []) {
    howlerPluginStore.addRoute({
      path: path,
      element: element,
      children: children
    });
  }

  /**
   * Adds a sitemap entry to the sitemap table, this is used to populate
   * information on the Breadcrumb component
   *
   * @param path The react router path to this route
   * @param title The title/label to display in breadcrumbs for this route
   * @param icon The icon component to show beside the title/label
   * @param isRoot When true, indicates that the breadcrumbs will reset to this one path each time it is encountered
   * @param isLeaf When true, indicates that this path does not aggregate in breadcrumbs, i.e. will be replaced by next path
   * @param excluded When true, indicates to breadcrumbs component to not render this route
   * @param breadcrumbs Static list of breadcrumb paths to be rendered for the given route
   * @param textWidth The max width of the text when rendering the breadcrumb
   */
  addSitemap(
    path: string,
    title: string,
    icon?: JSX.Element,
    isRoot?: boolean,
    isLeaf?: boolean,
    excluded?: boolean,
    breadcrumbs?: string[],
    textWidth?: number
  ) {
    if (isRoot === isLeaf) {
      throw new Error(`Sitemap '${path}' must define either isRoot or isLeaf as true`);
    }

    if (isRoot) {
      if (breadcrumbs != null) {
        breadcrumbs = null;
        // eslint-disable-next-line no-console
        console.warn(`Sitemap '${path}' with isRoot should not contain breadcrumbs and have been removed`);
      }
    }

    howlerPluginStore.addSitemap({
      path: path,
      title: title,
      icon: icon,
      isRoot: isRoot,
      isLeaf: isLeaf,
      excluded: excluded,
      breadcrumbs: breadcrumbs,
      textWidth: textWidth
    });
  }

  /**
   * Adds a route as well as a simple sitemap entry with values derived from the path
   *
   * @param path Route path, should not start with /
   * @param element Element the route directs to
   * @param children Child routes if required
   * @param title The title/label to display in breadcrumbs for this route
   * @param icon The icon component to show beside the title/label
   */
  addRouteAndSitemap(path: string, element: JSX.Element, title: string, icon?: JSX.Element, children?: []) {
    this.addRoute(path, element, children);

    const routeParts = path.split('/');

    let isRoot = true;
    let isLeaf = false;
    let breadcrumbs = null;

    if (routeParts.length > 1) {
      // Set as leaf and not root
      isRoot = false;
      isLeaf = true;
      // Attempt to auto build breadcrumbs
      breadcrumbs = [];
      for (let index = 0; index < routeParts.length - 1; index++) {
        breadcrumbs.push(`/${routeParts[index]}`);
      }
    }

    this.addSitemap(`/${path}`, title, icon, isRoot, isLeaf, false, breadcrumbs);
  }

  /**
   * Adds a new menu item to the Main Menu
   *
   * @param operation Insert operation to perform
   * @param targetId Reference Menu Id
   * @param id Identifier for new menu entry
   * @param i18nKey Translation key for new menu entry
   * @param route Route for new menu entry
   * @param icon Icon for new menu entry
   */
  addMainMenuItem(
    operation: MainMenuInsertOperation,
    targetId: string,
    id: string,
    i18nKey: string,
    route: string,
    icon: JSX.Element
  ) {
    if (targetId === '') {
      targetId = 'root';
    }

    howlerPluginStore.addMainMenuItem({
      operation: operation,
      targetId: targetId,
      item: {
        type: 'item',
        element: {
          id: id,
          i18nKey: i18nKey,
          route: route,
          icon: icon
        }
      }
    });
  }

  /**
   * Adds a divider to the main menu
   *
   * @param operation Insert operation to perform
   * @param targetId Reference menu id
   */
  addMainMenuDivider(operation: MainMenuInsertOperation, targetId: string) {
    if (targetId === '') {
      targetId = 'root';
    }

    howlerPluginStore.addMainMenuItem({
      operation: operation,
      targetId: targetId,
      item: {
        type: 'divider',
        element: null
      }
    });
  }

  addOperation(
    format: string,
    form: (props: CustomActionProps) => React.ReactNode,
    documentation: PluginDocumentation
  ) {
    if (!howlerPluginStore.addOperation(format)) {
      // eslint-disable-next-line no-console
      console.error(`Operation ${format} already configured, not enabling for plugin ${this.getPluginName()}`);
      return;
    }

    this.pluginStore.addFunction(`operation.${format}`, form);
    this.functionsToRemove.push(`operation.${format}`);

    this.pluginStore.addFunction(`operation.${format}.documentation`, () => documentation);
    this.functionsToRemove.push(`operation.${format}.documentation`);

    // eslint-disable-next-line no-console
    console.debug(`Operation ${format} enabled for plugin ${this.getPluginName()}`);
  }

  on(_event: string, _hit: Hit) {
    return null;
  }

  provider(): React.FC<PropsWithChildren<{}>> | null {
    return null;
  }

  setup(): void {}

  localization(_i18n: I18N): void {}

  helpers(): HowlerHelper[] {
    return [];
  }

  typography(_props: PluginTypographyProps) {
    return null;
  }

  chip(_props: PluginChipProps) {
    return null;
  }

  actions(_hits: Hit[]): ActionButton[] {
    return [];
  }

  status(_props: StatusProps): React.ReactNode {
    return null;
  }

  support(): React.ReactNode {
    return null;
  }

  help(): React.ReactNode {
    return null;
  }

  settings(_section: 'admin' | 'local' | 'profile' | 'security'): React.ReactNode {
    return null;
  }

  integrations(): [string, () => React.ReactNode][] {
    return [];
  }

  documentation(md: string): string {
    return md;
  }
}

export default HowlerPlugin;

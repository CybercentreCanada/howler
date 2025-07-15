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
import howlerPluginStore from './store';

const INTERNAL_FUNCTIONS = [
  'constructor',
  'getPluginName',
  'getDependencies',
  'init',
  'activate',
  'deactivate',
  'addLead'
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
}

export default HowlerPlugin;

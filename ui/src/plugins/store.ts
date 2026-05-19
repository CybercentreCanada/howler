/* eslint-disable no-console */
import type { LeftNavMenuItem } from '@tui/core';
import type { Hit } from 'models/entities/generated/Hit';
import type { ReactElement } from 'react';
import { createPluginStore, Event } from 'react-pluggable';
import type HowlerPlugin from './HowlerPlugin';

export class HitEvent extends Event {
  public hit: Hit;

  constructor(type: string, hit: Hit) {
    super(type);

    this.hit = hit;
  }
}

export type MainMenuOperation =
  | { type: 'append'; parentId: string; item: LeftNavMenuItem }
  | { type: 'insertRelative'; anchorId: string; position: 'before' | 'after'; item: LeftNavMenuItem }
  | { type: 'remove'; targetId: string };

export type MainMenuItemOperation = Exclude<MainMenuOperation, { type: 'remove' }>;

export type SiteMapRoute = {
  path: string;
  title: string;
  icon?: ReactElement;
  isRoot?: boolean;
  isLeaf?: boolean;
  excluded?: boolean;
  breadcrumbs?: string[];
  textWidth?: number;
};

class HowlerPluginStore {
  private _pluginStore = createPluginStore();

  plugins: string[] = [];

  private _leadFormats: string[] = [];
  private _pivotFormats: string[] = [];
  private _operations: string[] = [];
  private _userMenuItems: { i18nKey: string; route: string; icon: ReactElement }[] = [];
  private _adminMenuItems: { i18nKey: string; route: string; icon: ReactElement }[] = [];
  private _mainMenuOperations: MainMenuOperation[] = [];
  private _routes: { path: string; element: ReactElement; children?: [] }[] = [];
  private _sitemaps: SiteMapRoute[] = [];

  install(plugin: HowlerPlugin) {
    if (this.plugins.includes(plugin.name)) {
      return;
    }

    console.log(`Installing plugin ${plugin.getPluginName()} by ${plugin.author}`);

    this.plugins.push(plugin.name);

    this.pluginStore.install(plugin);
  }

  addLead(format: string): boolean {
    if (this._leadFormats.includes(format)) {
      return false;
    }

    this._leadFormats.push(format);

    return true;
  }

  addPivot(format: string): boolean {
    if (this._pivotFormats.includes(format)) {
      return false;
    }

    this._pivotFormats.push(format);

    return true;
  }

  addUserMenuItem(menuItem: { i18nKey: string; route: string; icon: ReactElement }) {
    this._userMenuItems.push(menuItem);
  }

  addAdminMenuItem(menuItem: { i18nKey: string; route: string; icon: ReactElement }) {
    this._adminMenuItems.push(menuItem);
  }

  addMainMenuOperation(menuOperation: MainMenuOperation) {
    this._mainMenuOperations.push(menuOperation);
  }

  addRoute(route: { path: string; element: ReactElement; children?: [] }) {
    this._routes.push(route);
  }

  addSitemap(sitemap: SiteMapRoute) {
    this._sitemaps.push(sitemap);
  }

  addOperation(format: string): boolean {
    if (this._operations.includes(format)) {
      return false;
    }

    this._operations.push(format);

    return true;
  }

  public get leadFormats() {
    return this._leadFormats;
  }

  public get pivotFormats() {
    return this._pivotFormats;
  }

  public get operations() {
    return this._operations;
  }

  public get userMenuItems() {
    return this._userMenuItems;
  }

  public get adminMenuItems() {
    return this._adminMenuItems;
  }

  public get mainMenuOperations(): readonly MainMenuOperation[] {
    return [...this._mainMenuOperations];
  }

  public get routes() {
    return this._routes;
  }

  public get sitemaps() {
    return this._sitemaps;
  }

  public get pluginStore() {
    return this._pluginStore;
  }
}

const howlerPluginStore = new HowlerPluginStore();

export default howlerPluginStore;

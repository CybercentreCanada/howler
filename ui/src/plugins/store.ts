/* eslint-disable no-console */
import type { Hit } from 'models/entities/generated/Hit';
import { createPluginStore, Event } from 'react-pluggable';
import type HowlerPlugin from './HowlerPlugin';
import type { AppLeftNavElement } from '../commons/components/app/AppConfigs';

export class HitEvent extends Event {
  public hit: Hit;

  constructor(type: string, hit: Hit) {
    super(type);

    this.hit = hit;
  }
}

export enum MainMenuInsertOperation {
  Insert = 'INSERT',
  InsertAfter = 'AFTER',
  InsertBefore = 'BEFORE'
}

class HowlerPluginStore {
  private _pluginStore = createPluginStore();

  plugins: string[] = [];

  private _leadFormats: string[] = [];
  private _pivotFormats: string[] = [];
  private _operations: string[] = [];
  private _userMenuItems: { i18nKey: string; route: string; icon: JSX.Element }[] = [];
  private _adminMenuItems: { i18nKey: string; route: string; icon: JSX.Element }[] = [];
  private _mainMenuOperations: { operation: string; targetId: string; item: AppLeftNavElement }[] = [];
  private _routes: { path: string; element: JSX.Element; children?: [] }[] = [];
  private _sitemaps: {
    path: string;
    title: string;
    icon?: JSX.Element;
    isRoot?: boolean;
    isLeaf?: boolean;
    excluded?: boolean;
    breadcrumbs?: string[];
    textWidth?: number;
  }[] = [];

  install(plugin: HowlerPlugin) {
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

  addUserMenuItem(menuItem: { i18nKey: string; route: string; icon: JSX.Element }) {
    this._userMenuItems.push(menuItem);
  }

  addAdminMenuItem(menuItem: { i18nKey: string; route: string; icon: JSX.Element }) {
    this._adminMenuItems.push(menuItem);
  }

  addMainMenuItem(menuOperation: { operation: string; targetId: string; item: AppLeftNavElement }) {
    this._mainMenuOperations.push(menuOperation);
  }

  addRoute(route: { path: string; element: JSX.Element; children?: [] }) {
    this._routes.push(route);
  }

  addSitemap(sitemap: {
    path: string;
    title: string;
    icon?: JSX.Element;
    isRoot?: boolean;
    isLeaf?: boolean;
    excluded?: boolean;
    breadcrumbs?: string[];
    textWidth?: number;
  }) {
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

  public get mainMenuOperations() {
    return this._mainMenuOperations;
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

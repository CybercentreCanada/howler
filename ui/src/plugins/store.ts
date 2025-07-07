/* eslint-disable no-console */
import type { Hit } from 'models/entities/generated/Hit';
import { createPluginStore, Event } from 'react-pluggable';
import type HowlerPlugin from './HowlerPlugin';

export class HitEvent extends Event {
  public hit: Hit;

  constructor(type: string, hit: Hit) {
    super(type);

    this.hit = hit;
  }
}

class HowlerPluginStore {
  private _pluginStore = createPluginStore();

  plugins: string[] = [];

  private _leadFormats: string[] = [];
  private _pivotFormats: string[] = [];
  private _operations: string[] = [];

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

  public get pluginStore() {
    return this._pluginStore;
  }
}

const howlerPluginStore = new HowlerPluginStore();

export default howlerPluginStore;

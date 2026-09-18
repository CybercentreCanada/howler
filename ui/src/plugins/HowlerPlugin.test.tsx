/// <reference types="vitest" />
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockHowlerPluginStore = vi.hoisted(() => ({
  addAdminMenuItem: vi.fn(),
  addLead: vi.fn(),
  addMainMenuOperation: vi.fn(),
  addOperation: vi.fn(),
  addPivot: vi.fn(),
  addRoute: vi.fn(),
  addUserMenuItem: vi.fn()
}));

vi.mock('./store', () => ({
  default: mockHowlerPluginStore
}));

vi.mock('i18n', () => ({
  default: { language: 'en' }
}));

import HowlerPlugin from './HowlerPlugin';

class TestPlugin extends HowlerPlugin {
  name = 'demo';
  version = '1.2.3';
  author = 'copilot';
  description = 'test plugin';

  localization = vi.fn();
  provider = vi.fn(() => null);
}

describe('HowlerPlugin', () => {
  const addFunction = vi.fn();
  const removeFunction = vi.fn();
  let plugin: TestPlugin;

  beforeEach(() => {
    vi.clearAllMocks();
    plugin = new TestPlugin();
    plugin.init({ addFunction, removeFunction } as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('formats the plugin name with its version', () => {
    expect(plugin.getPluginName()).toBe('demo@1.2.3');
    expect(plugin.getDependencies()).toEqual([]);
  });

  it('registers extension hooks and calls localization on activation', () => {
    plugin.activate();

    expect(addFunction).toHaveBeenCalledWith('demo.provider', expect.any(Function));
    expect(addFunction).toHaveBeenCalledWith('demo.localization', expect.any(Function));
    expect(plugin.localization).toHaveBeenCalledWith({ language: 'en' });
  });

  it('removes registered extension hooks on deactivation', () => {
    plugin.activate();
    plugin.deactivate();

    expect(removeFunction).toHaveBeenCalledWith('demo.provider');
    expect(removeFunction).toHaveBeenCalledWith('demo.localization');
  });

  it('adds lead renderers and forms when the lead format is available', () => {
    mockHowlerPluginStore.addLead.mockReturnValue(true);
    const renderer = vi.fn();
    const form = vi.fn();

    plugin.addLead('markdown', form, renderer);

    expect(mockHowlerPluginStore.addLead).toHaveBeenCalledWith('markdown');
    expect(addFunction).toHaveBeenCalledWith('lead.markdown', renderer);
    expect(addFunction).toHaveBeenCalledWith('lead.markdown.form', form);
  });

  it('skips duplicate lead formats', () => {
    mockHowlerPluginStore.addLead.mockReturnValue(false);
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    plugin.addLead('markdown', vi.fn(), vi.fn());

    expect(addFunction).not.toHaveBeenCalledWith('lead.markdown', expect.any(Function));
    expect(errorSpy).toHaveBeenCalledWith('Lead format markdown already configured, not enabling for plugin demo@1.2.3');
  });

  it('adds pivots, routes, menu items, and operations through the plugin store', () => {
    mockHowlerPluginStore.addPivot.mockReturnValue(true);
    mockHowlerPluginStore.addOperation.mockReturnValue(true);
    const element = { type: 'icon' } as ReactElement;

    plugin.addPivot('link', vi.fn(), vi.fn());
    plugin.addUserMenuItem('menu.user', '/me', element);
    plugin.addAdminMenuItem('menu.admin', '/admin', element);
    plugin.addRoute('custom', element, []);
    plugin.addMainMenuItem({ type: 'append', parentId: 'root', item: { id: 'new-item' } as any });
    plugin.addOperation('custom', vi.fn(), { title: 'Docs', description: 'Help' } as any);

    expect(mockHowlerPluginStore.addPivot).toHaveBeenCalledWith('link');
    expect(addFunction).toHaveBeenCalledWith('pivot.link', expect.any(Function));
    expect(addFunction).toHaveBeenCalledWith('pivot.link.form', expect.any(Function));
    expect(mockHowlerPluginStore.addUserMenuItem).toHaveBeenCalledWith({ i18nKey: 'menu.user', route: '/me', icon: element });
    expect(mockHowlerPluginStore.addAdminMenuItem).toHaveBeenCalledWith({
      i18nKey: 'menu.admin',
      route: '/admin',
      icon: element
    });
    expect(mockHowlerPluginStore.addRoute).toHaveBeenCalledWith({ path: 'custom', element, children: [] });
    expect(mockHowlerPluginStore.addMainMenuOperation).toHaveBeenCalledWith({
      type: 'append',
      parentId: 'root',
      item: { id: 'new-item' }
    });
    expect(mockHowlerPluginStore.addOperation).toHaveBeenCalledWith('custom');
    expect(addFunction).toHaveBeenCalledWith('operation.custom', expect.any(Function));
    expect(addFunction).toHaveBeenCalledWith('operation.custom.documentation', expect.any(Function));
  });
});

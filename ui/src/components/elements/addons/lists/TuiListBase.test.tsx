/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';
import { createContext } from 'react';
import { describe, expect, it, vi } from 'vitest';

const registerSpy = vi.hoisted(() => vi.fn(() => vi.fn()));

vi.mock('@mui/material', () => ({
  emphasize: (_color: string, value: number) => `emphasis-${value}`,
  styled: (tag: any) => (styles: any) => {
    styles({
      theme: {
        palette: { background: { default: '#fff' }, text: { disabled: '#999' } }
      }
    });
    return tag;
  }
}));

vi.mock('@tui/core', () => ({
  useAppBar: () => ({ autoHide: true }),
  useAppBarHeight: () => 42,
  useAppLayout: () => ({ current: 'wide' })
}));

vi.mock('components/elements/addons/lists/hooks/useTuiListKeyboard', () => ({
  default: () => ({ register: registerSpy })
}));

import TuiListBase from './TuiListBase';
import { TuiListItemsContext, TuiListMethodContext } from './TuiListProvider';

describe('TuiListBase', () => {
  it('renders items, exposes layout metadata, and forwards selection', () => {
    const onSelect = vi.fn();
    const select = vi.fn(item => ({ ...item, selected: !item.selected, cursor: true }));

    render(
      <TuiListMethodContext.Provider value={{ select } as any}>
        <TuiListItemsContext.Provider value={{ items: [{ id: '1', item: 'one', selected: false, cursor: false }] } as any}>
          <TuiListBase onSelect={onSelect}>
            {(items, handleSelect) => (
              <div>
                <button onClick={() => handleSelect(items[0], 0)}>pick</button>
                <div>{items[0].item as any}</div>
              </div>
            )}
          </TuiListBase>
        </TuiListItemsContext.Provider>
      </TuiListMethodContext.Provider>
    );

    const root = screen.getByText('one').closest('[data-tuiappbar-height]');
    expect(root).toHaveAttribute('data-tuiappbar-height', '42');
    expect(root).toHaveAttribute('data-tuilayout', 'wide');
    expect(root).toHaveAttribute('data-tuiappbar-autohide', 'true');

    screen.getByText('pick').click();
    expect(select).toHaveBeenCalledWith({ id: '1', item: 'one', selected: false, cursor: false }, 0);
    expect(onSelect).toHaveBeenCalledWith({ id: '1', item: 'one', selected: true, cursor: true }, 0);
  });

  it('registers keyboard handlers when keyboard mode is enabled', () => {
    render(
      <TuiListMethodContext.Provider value={{ select: vi.fn(item => item) } as any}>
        <TuiListItemsContext.Provider value={{ items: [] } as any}>
          <TuiListBase keyboard onSelect={vi.fn()}>
            {() => <div>content</div>}
          </TuiListBase>
        </TuiListItemsContext.Provider>
      </TuiListMethodContext.Provider>
    );

    expect(registerSpy).toHaveBeenCalled();
  });
});

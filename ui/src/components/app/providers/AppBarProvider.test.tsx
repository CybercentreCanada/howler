/// <reference types="vitest" />
import { act, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it } from 'vitest';

import AppBarProvider, { AppBarContext } from './AppBarProvider';

const Consumer = () => {
  const ctx = useContext(AppBarContext);
  return (
    <div>
      <button onClick={() => ctx.addToAppBar('left', 'a', <span>A</span>)}>add-left</button>
      <button onClick={() => ctx.addToAppBar('right', 'b', <span>B</span>)}>add-right</button>
      <button onClick={() => ctx.addToAppBar('left', 'a', <span>A2</span>)}>add-duplicate</button>
      <button onClick={() => ctx.removeFromAppBar('a')}>remove-left</button>
      <span>{ctx.leftItems.map(item => item.id).join(',')}</span>
      <span>{ctx.rightItems.map(item => item.id).join(',')}</span>
    </div>
  );
};

describe('AppBarProvider', () => {
  it('adds unique app bar items and removes them from both sides', async () => {
    render(
      <AppBarProvider>
        <Consumer />
      </AppBarProvider>
    );

    await act(async () => screen.getByText('add-left').click());
    await act(async () => screen.getByText('add-right').click());
    await act(async () => screen.getByText('add-duplicate').click());
    expect(screen.getByText('a')).toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();

    await act(async () => screen.getByText('remove-left').click());
    expect(screen.queryByText(/^a$/)).not.toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();
  });
});

/// <reference types="vitest" />
import { fireEvent, render, screen } from '@testing-library/react';
import { useContext } from 'react';
import { describe, expect, it } from 'vitest';

import TuiListProvider, { TuiListItemsContext, TuiListMethodContext } from './TuiListProvider';

const Probe = () => {
  const methods = useContext(TuiListMethodContext);
  const { items, moveNext, movePrevious } = useContext(TuiListItemsContext);

  return (
    <div>
      <button onClick={() => methods.load([{ id: '1', item: 'one', selected: false, cursor: false }])}>load-one</button>
      <button
        onClick={() =>
          methods.load([
            { id: '1', item: 'updated', selected: undefined as any, cursor: undefined as any, details: undefined as any },
            { id: '2', item: 'two', selected: false, cursor: false }
          ])
        }
      >
        merge-load
      </button>
      <button
        onClick={() =>
          methods.load([
            { id: '1', item: 'one', selected: false, cursor: false },
            { id: '2', item: 'two', selected: false, cursor: false }
          ])
        }
      >
        load-two
      </button>
      <button onClick={() => methods.select(items[0], 0)}>select-first</button>
      <button onClick={() => methods.move(1)}>move-second</button>
      <button onClick={() => methods.replace(items[0], { id: '1', item: 'replace-ref', details: 'details' } as any)}>replace-ref</button>
      <button onClick={() => methods.replaceById({ id: '2' } as any, { id: '2', item: 'replace-id' } as any)}>replace-id</button>
      <button onClick={() => methods.remove('1')}>remove-first</button>
      <button onClick={() => moveNext()}>move-next</button>
      <button onClick={() => movePrevious()}>move-previous</button>
      <pre>{JSON.stringify(items)}</pre>
    </div>
  );
};

describe('TuiListProvider', () => {
  it('loads, preserves state, selects, moves, replaces, and removes items', () => {
    render(
      <TuiListProvider>
        <Probe />
      </TuiListProvider>
    );

    fireEvent.click(screen.getByText('load-one'));
    expect(screen.getByText('[{"id":"1","item":"one","selected":false,"cursor":false}]')).toBeInTheDocument();

    fireEvent.click(screen.getByText('select-first'));
    expect(screen.getByText('[{"id":"1","item":"one","selected":true,"cursor":true}]')).toBeInTheDocument();

    fireEvent.click(screen.getByText('merge-load'));
    expect(screen.getByText('[{"id":"1","item":"updated","selected":true,"cursor":true},{"id":"2","item":"two","selected":false,"cursor":false}]')).toBeInTheDocument();

    fireEvent.click(screen.getByText('replace-ref'));
    expect(
      screen.getByText('[{"id":"1","item":"replace-ref","selected":true,"cursor":true,"details":"details"},{"id":"2","item":"two","selected":false,"cursor":false}]')
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText('replace-id'));
    expect(
      screen.getByText('[{"id":"1","item":"replace-ref","selected":true,"cursor":true,"details":"details"},{"id":"2","item":"replace-id","selected":false,"cursor":false}]')
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText('remove-first'));
    expect(screen.getByText('[{"id":"2","item":"replace-id","selected":false,"cursor":false}]')).toBeInTheDocument();
  });

  it('supports move and wraparound keyboard helpers', () => {
    render(
      <TuiListProvider>
        <Probe />
      </TuiListProvider>
    );

    fireEvent.click(screen.getByText('load-two'));
    fireEvent.click(screen.getByText('move-second'));
    expect(screen.getByText('[{"id":"1","item":"one","selected":false,"cursor":false},{"id":"2","item":"two","selected":false,"cursor":true}]')).toBeInTheDocument();

    fireEvent.click(screen.getByText('move-next'));
    expect(screen.getByText('[{"id":"1","item":"one","selected":false,"cursor":true},{"id":"2","item":"two","selected":false,"cursor":false}]')).toBeInTheDocument();

    fireEvent.click(screen.getByText('move-previous'));
    expect(screen.getByText('[{"id":"1","item":"one","selected":false,"cursor":false},{"id":"2","item":"two","selected":false,"cursor":true}]')).toBeInTheDocument();
  });
});

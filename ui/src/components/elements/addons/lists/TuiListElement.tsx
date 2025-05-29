import { memo, useCallback, useRef } from 'react';
import { type TuiListItem, type TuiListItemOnSelect, type TuiListItemRenderer } from '.';
import VSBoxElement from '../layout/vsbox/VSBoxElement';

type TuiListElementProps<T> = {
  position: number;
  item: TuiListItem<T>;
  onSelect?: TuiListItemOnSelect<T>;
  children: TuiListItemRenderer<T>;
};

const TuiListElement = <T,>({ position, item, onSelect: onClick, children }: TuiListElementProps<T>) => {
  const elementEl = useRef<HTMLDivElement>();

  const onItemClick = useCallback(
    _event => {
      if (onClick) {
        onClick(item, position);
      }
    },
    [onClick, item, position]
  );

  const classRenderer = useCallback(() => {
    const _classes = ['elementHover'];
    if (item.cursor) {
      _classes.push('elementFocus');
    }
    if (item.selected) {
      _classes.push('elementSelected');
    }
    return _classes.join(' ');
  }, [item.cursor, item.selected]);

  return (
    <VSBoxElement focus={!!item.cursor}>
      <div
        ref={elementEl}
        data-tuilist-index={position}
        data-tuilist-id={item.id}
        data-tuilist-focus={!!item.cursor}
        data-tuilist-selected={!!item.selected}
        onClick={onItemClick}
      >
        {children({ item, position }, classRenderer)}
      </div>
    </VSBoxElement>
  );
};

export default memo(TuiListElement);

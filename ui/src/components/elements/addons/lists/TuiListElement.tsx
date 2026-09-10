import { memo, useCallback, useRef, type MouseEvent } from 'react';
import type { TuiListItem, TuiListItemOnSelect, TuiListItemRenderer } from '.';
import VSBoxElement from '../layout/vsbox/VSBoxElement';

type TuiListElementProps<T> = {
  position: number;
  item: TuiListItem<T>;
  onSelect?: TuiListItemOnSelect<T>;
  children: TuiListItemRenderer<T>;
};

const TuiListElement = <T,>({ position, item, onSelect: onClick, children }: TuiListElementProps<T>) => {
  const elementEl = useRef<HTMLDivElement>(null);

  const onItemClick = useCallback(
    (_event: MouseEvent<HTMLDivElement>) => {
      if (onClick && !item.disabled) {
        onClick(item, position);
      }
    },
    [onClick, item, position]
  );

  const classRenderer = useCallback(() => {
    if (item.disabled) {
      return 'elementDisabled';
    }

    const _classes = ['elementHover'];
    if (item.cursor) {
      _classes.push('elementFocus');
    }
    if (item.selected) {
      _classes.push('elementSelected');
    }
    return _classes.join(' ');
  }, [item.cursor, item.selected, item.disabled]);

  return (
    <VSBoxElement focus={!!item.cursor}>
      <div
        ref={elementEl}
        data-tuilist-index={position}
        data-tuilist-id={item.id}
        data-tuilist-focus={!!item.cursor}
        data-tuilist-selected={!!item.selected}
        aria-disabled={item.disabled}
        onClick={onItemClick}
      >
        {children({ item, position }, classRenderer)}
      </div>
    </VSBoxElement>
  );
};

export default memo(TuiListElement) as typeof TuiListElement;

import AppListEmpty from 'commons/components/display/AppListEmpty';
import { memo } from 'react';
import type { TuiListItemOnSelect, TuiListItemRenderer } from '.';
import TuiListBase from './TuiListBase';
import TuiListElement from './TuiListElement';

type TuiListProps<T> = {
  keyboard?: boolean;
  children: TuiListItemRenderer<T>;
  onSelection?: TuiListItemOnSelect<T>;
};

const TuiList = <T,>({ keyboard, children, onSelection }: TuiListProps<T>) => {
  return (
    <TuiListBase keyboard={keyboard} onSelect={onSelection}>
      {(items, onSelect) =>
        items && items.length > 0 ? (
          items.map((element, i) => (
            <TuiListElement key={element.id} position={i} item={element} onSelect={onSelect}>
              {children}
            </TuiListElement>
          ))
        ) : (
          <AppListEmpty />
        )
      }
    </TuiListBase>
  );
};

export default memo(TuiList);

import type { AppSearchServiceState } from 'commons/components/app/AppContexts';
import type { ReactElement } from 'react';

export type AppSearchMode = 'inline' | 'fullscreen';

export type AppSearchItem<T = any> = {
  id: string | number;
  item: T;
};

export type AppSearchItemRendererOption<T = any> = {
  state: AppSearchServiceState<T>;
  index: number;
  last: boolean;
};

export type AppSearchService<T = any> = {
  // Called once when the search input component has mounted.
  // You can use this to prefill the search input and search results.
  onMounted?: (setValue?: (value: string) => void, state?: AppSearchServiceState<T>) => void;
  // Handler for when the search input receives an 'Enter' key keyboard event.
  onEnter?: (value: string, state?: AppSearchServiceState<T>, setValue?: (value: string) => void) => void;
  // Handler for when the value of the search input component changes.
  onChange?: (value: string, state: AppSearchServiceState<T>, setValue?: (value: string) => void) => void;
  // Handler for when a search item has focus and receives an 'Enter' key keyboard event.
  onItemSelect?: (item: AppSearchItem<T>, state?: AppSearchServiceState<T>) => void;
  // Search result item renderer.
  itemRenderer: (item: AppSearchItem<T>, options?: AppSearchItemRendererOption<T>) => ReactElement;
  // Search result header renderer.
  headerRenderer?: (state: AppSearchServiceState<T>) => ReactElement;
  // Search result footer renderer.
  footerRenderer?: (state: AppSearchServiceState<T>) => ReactElement;
};

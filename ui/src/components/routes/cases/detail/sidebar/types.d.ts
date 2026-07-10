import type { Item } from 'models/entities/generated/Item';

export type Tree = {
  item: Item;
  leaves?: Item[];
  folders?: {
    [key: string]: Tree;
  };
};

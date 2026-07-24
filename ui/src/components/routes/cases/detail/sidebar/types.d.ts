import type { Item } from 'models/entities/generated/Item';

export type Tree = {
  item: Item | null;
  leaves?: Item[];
  folders?: {
    [key: string]: Tree;
  };
};

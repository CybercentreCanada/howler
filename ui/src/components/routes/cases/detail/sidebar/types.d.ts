import type { Item } from 'models/entities/generated/Item';

export type Tree = {
  path: string;
  leaves?: Item[];
  folders?: {
    [key: string]: Tree;
  };
};

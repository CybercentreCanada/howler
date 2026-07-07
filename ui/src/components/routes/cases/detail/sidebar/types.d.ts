import type { Item } from 'models/entities/generated/Item';

export type Tree = {
  id?: string;
  parentId?: string | null;
  leaves?: Item[];
  folders?: {
    [key: string]: Tree;
  };
};

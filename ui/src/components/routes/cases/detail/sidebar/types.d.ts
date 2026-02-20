import type { Item } from 'models/entities/generated/Item';

export type Tree = { leaves?: Item[]; [folder: string]: Tree | Item[] };

import type { Item } from 'models/entities/generated/Item';

export type Tree = { __path: string; leaves?: Item[]; [folder: string]: Tree | Item[] };

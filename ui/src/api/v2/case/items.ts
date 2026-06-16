// eslint-disable-next-line import/no-cycle
import { hdelete, hpost, hput, joinUri } from 'api';
import { uri as parentUri } from 'api/v2/case';

import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';

export const uri = (id: string) => {
  return joinUri(parentUri(id), 'items');
};

export const post = (id: string, newData: Item): Promise<Case> => {
  // Case items must always be placed at the root of the case structure.
  // If a nested path is provided, strip folder segments and retain only the last component,
  // then warn so callers know a normalization occurred.
  if (newData.type === 'case' && newData.path?.includes('/')) {
    const normalizedPath = newData.path.replace(/\/+$/, '').split('/').pop() || newData.value;

    newData = { ...newData, path: normalizedPath };
  }

  return hpost(uri(id), newData);
};

export const del = (id: string, values: string | string[]): Promise<Case> => {
  if (!Array.isArray(values)) {
    values = [values];
  }

  return hdelete(uri(id), { values });
};

export const put = (id: string, value: string, newPath: string): Promise<Case> => {
  return hput(uri(id), { value, new_path: newPath });
};

import { get } from 'lodash-es';

export const nameToInitials = (string: string) => {
  const parts = string.split(' ').slice(0, 2);

  if (string.includes(',')) {
    parts.reverse();
  }

  return parts.map(p => p.charAt(0).toUpperCase());
};

export const maxLenStr = (str: string, len: number) => {
  if (str.length > len) {
    return `${str.substr(0, len - 3)}...`;
  }
  return str;
};

export const safeFieldValue = (data: string | number | boolean) => {
  const temp = String(data);
  return `"${temp.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
};

export const safeFieldValueURI = (data: string | number | boolean) => {
  return `${encodeURIComponent(safeFieldValue(data))}`;
};

export const sanitizeLuceneQuery = (query: string) => {
  return query
    .replace(/([\^"~*?:\\/()[\]{}\-!])/g, '\\$1')
    .replace('&&', '\\&&')
    .replace('||', '\\||');
};

// Supports : prop or any form of nested object.. prop.object.prop2, prop.object[0].prop2
export const safeStringPropertyCompare = (propertyPath: string) => {
  return (a: unknown, b: unknown) => {
    const aVal = get(a, propertyPath);
    const bVal = get(b, propertyPath);
    return aVal && bVal ? aVal.localeCompare(bVal) : aVal ? 1 : 0;
  };
};

export const sanitizeMultilineLucene = (query: string) => {
  return query.replace(/#.+/g, '').replace(/\n{2,}/, '\n');
};

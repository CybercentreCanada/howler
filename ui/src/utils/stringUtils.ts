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

// Decode escaped literals, not full Lucene expressions; original escape spelling is not retained.
export const unescapeLucene = (value: string) => value.replace(/\\(.)/gs, '$1');

// Sticky matching consumes every character without repeatedly slicing the remaining clause.
export const parseQuotedValues = (value: string): string[] | null => {
  const unwrappedClause = value.replace(/^\((.*)\)$/s, '$1');
  const clause = unwrappedClause.trim();
  const parts: string[] = [];
  const quoted = /"((?:\\.|[^"\\])*)"/sy;
  const separator = /\s+OR\s+/y;
  let offset = 0;

  while (offset < clause.length) {
    quoted.lastIndex = offset;
    const match = quoted.exec(clause);
    if (!match) {
      return null;
    }

    parts.push(unescapeLucene(match[1] ?? ''));
    offset = quoted.lastIndex;

    if (offset === clause.length) {
      return parts;
    }

    if (unwrappedClause === value) {
      return null;
    }

    separator.lastIndex = offset;

    if (!separator.exec(clause)) {
      return null;
    }

    offset = separator.lastIndex;
  }

  return null;
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

export const validateRegex = (regex: string) => {
  try {
    new RegExp(regex);

    return true;
  } catch {
    return false;
  }
};

export const parsePixelSizeStringToInt = (size: string) => {
  const match = size.match(/^(\d+(\.\d+)?)(px)?$/);
  if (match) {
    return parseInt(match[1]);
  }
  return null;
};

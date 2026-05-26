import Handlebars from 'handlebars';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import { flattenDeep } from 'utils/utils';

const ResolvePivotUrl = (pivot: NonNullable<Dossier['pivots']>[number], currentHit?: Hit): string => {
  const flatHit = flattenDeep(currentHit ?? {});

  const templateObject = Object.fromEntries(
    (pivot.mappings ?? []).map(mapping => {
      const value =
        mapping.field === 'custom'
          ? mapping.custom_value
          : Array.isArray(flatHit[mapping.field])
            ? flatHit[mapping.field][0]
            : flatHit[mapping.field];

      return [mapping.key, value];
    })
  );

  try {
    return Handlebars.compile(pivot.value)(templateObject);
  } catch {
    return pivot.value;
  }
};

export default ResolvePivotUrl;

import type { HowlerHelper } from 'components/elements/display/handlebars/helpers';
import Handlebars from 'handlebars';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useEffect, useRef, useState } from 'react';
import { flattenDeep } from 'utils/utils';

const CLOSE_DELAY = 200;

export const useHoverMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [shouldFocusMenu, setShouldFocusMenu] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  const openMenu = useCallback((focusMenu = false) => {
    clearTimeout(closeTimer.current);
    setShouldFocusMenu(focusMenu);
    setIsOpen(true);
  }, []);

  const cancelClose = useCallback(() => clearTimeout(closeTimer.current), []);

  const scheduleClose = useCallback((delay = CLOSE_DELAY) => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setIsOpen(false), delay);
  }, []);

  const closeMenu = useCallback(() => {
    clearTimeout(closeTimer.current);
    setShouldFocusMenu(false);
    setIsOpen(false);
  }, []);

  return { isOpen, shouldFocusMenu, openMenu, cancelClose, scheduleClose, closeMenu };
};

export const resolvePivotUrl = (
  pivot: NonNullable<Dossier['pivots']>[number],
  currentHit?: Hit,
  helpers: HowlerHelper[] = []
): string => {
  const flatHit = flattenDeep(currentHit ?? {});
  const handlebars = Handlebars.create();

  helpers.forEach(helper => {
    if (helper.callback && !handlebars.helpers[helper.keyword]) {
      handlebars.registerHelper(helper.keyword, helper.callback);
    }
  });

  const templateObject = Object.fromEntries(
    (pivot.mappings ?? []).map(mapping => {
      const value =
        mapping.field === 'custom'
          ? mapping.custom_value
          : Array.isArray(flatHit[mapping.field!])
            ? flatHit[mapping.field!][0]
            : flatHit[mapping.field!];

      return [mapping.key, value];
    })
  );

  try {
    return handlebars.compile(pivot.value)(templateObject);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(`Failed to compile pivot template for value "${pivot.value}":`, e);
    return pivot.value!;
  }
};

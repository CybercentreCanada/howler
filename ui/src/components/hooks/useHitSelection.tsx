import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import type { Hit } from 'models/entities/generated/Hit';
import type React from 'react';
import { useCallback, useState } from 'react';
import { useContextSelector } from 'use-context-selector';

const useHitSelection = () => {
  const response = useContextSelector(HitSearchContext, ctx => ctx.response);
  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);
  const addHitToSelection = useContextSelector(HitContext, ctx => ctx.addHitToSelection);
  const removeHitFromSelection = useContextSelector(HitContext, ctx => ctx.removeHitFromSelection);
  const clearSelectedHits = useContextSelector(HitContext, ctx => ctx.clearSelectedHits);

  const setSelected = useContextSelector(ParameterContext, ctx => ctx.setSelected);

  const [lastSelected, setLastSelected] = useState<string>(null);

  const onClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>, hit: Hit) => {
      setLastSelected(hit.howler.id);

      if (e.ctrlKey) {
        document.getSelection().removeAllRanges();

        if (selectedHits.some(_hit => _hit.howler.id === hit.howler.id)) {
          removeHitFromSelection(hit.howler.id);
        } else {
          addHitToSelection(hit.howler.id);
        }

        e.stopPropagation();
        return;
      }

      if (e.shiftKey) {
        document.getSelection().removeAllRanges();

        if (selectedHits.length < 1) {
          addHitToSelection(hit.howler.id);
        } else if (lastSelected) {
          const lastSelectedIndex = response?.items.findIndex(_hit => _hit.howler.id === lastSelected);
          const currentIndex = response?.items.findIndex(_hit => _hit.howler.id === hit.howler.id);

          const lowerBound = lastSelectedIndex < currentIndex ? lastSelectedIndex : currentIndex;
          const upperBound = lastSelectedIndex > currentIndex ? lastSelectedIndex : currentIndex;

          for (let i = lowerBound; i <= upperBound; i++) {
            addHitToSelection(response.items[i]?.howler.id);
          }
        }

        e.stopPropagation();
        return;
      }

      clearSelectedHits(hit.howler.id);
      setSelected(hit.howler.id);
    },
    [
      addHitToSelection,
      clearSelectedHits,
      lastSelected,
      removeHitFromSelection,
      response?.items,
      selectedHits,
      setSelected
    ]
  );

  return { lastSelected, setLastSelected, onClick };
};

export default useHitSelection;

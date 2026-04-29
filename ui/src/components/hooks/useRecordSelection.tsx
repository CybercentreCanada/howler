import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import type { Hit } from 'models/entities/generated/Hit';
import type React from 'react';
import { useCallback, useState } from 'react';
import { useContextSelector } from 'use-context-selector';

const useRecordSelection = () => {
  const response = useContextSelector(RecordSearchContext, ctx => ctx.response);
  const selectedHits = useContextSelector(RecordContext, ctx => ctx.selectedRecords);
  const addHitToSelection = useContextSelector(RecordContext, ctx => ctx.addRecordToSelection);
  const removeHitFromSelection = useContextSelector(RecordContext, ctx => ctx.removeRecordFromSelection);
  const clearSelectedHits = useContextSelector(RecordContext, ctx => ctx.clearSelectedRecords);

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

export default useRecordSelection;

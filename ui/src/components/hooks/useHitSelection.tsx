import type { AppSiteMapRoute } from 'commons/components/app/AppConfigs';
import { useAppBreadcrumbs } from 'commons/components/app/hooks';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import useMySitemap from 'components/hooks/useMySitemap';
import type { Hit } from 'models/entities/generated/Hit';
import type React from 'react';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

const useHitSelection = () => {
  const navigate = useNavigate();

  const { setItems } = useAppBreadcrumbs();
  const { routes } = useMySitemap();

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

      if (hit.howler.is_bundle) {
        const searchRoute = routes.find(_route =>
          _route.path.startsWith(location.pathname.replace(/^(\/.*)\/.+/, '$1'))
        );

        const newBreadcrumb: AppSiteMapRoute = {
          ...searchRoute,
          path: location.pathname + location.search
        };
        setItems([{ route: newBreadcrumb, matcher: null }]);

        navigate(`/bundles/${hit.howler.id}?span=date.range.all&query=howler.id%3A*&offset=0`);
        clearSelectedHits(hit.howler.id);
      } else {
        clearSelectedHits(hit.howler.id);
        setSelected(hit.howler.id);
      }
    },
    [
      addHitToSelection,
      clearSelectedHits,
      lastSelected,
      navigate,
      removeHitFromSelection,
      response,
      routes,
      selectedHits,
      setItems,
      setSelected
    ]
  );

  return { lastSelected, setLastSelected, onClick };
};

export default useHitSelection;

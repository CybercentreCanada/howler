import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import NotFoundPage from 'components/routes/404';
import InformationPane from 'components/routes/hits/search/InformationPane';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useOutletContext, useParams } from 'react-router-dom';
import useCase from '../hooks/useCase';
import CaseDashboard from './CaseDashboard';

const ItemPage: FC<{ case?: Case }> = ({ case: providedCase }) => {
  const params = useParams();
  const routeCase = useOutletContext<Case>();
  const { case: fetchedCase } = useCase({ caseId: !providedCase && !routeCase ? params.id : undefined });
  const _case = providedCase ?? routeCase ?? fetchedCase;

  const { dispatchApi } = useMyApi();

  const [item, setItem] = useState<Item>(null);
  const [loading, setLoading] = useState(true);

  // When rendered as a child route, the wildcard segment is in params['*'].
  const subPath = params['*'] ?? '';

  // Item IDs separated by '/' for nested case traversal
  const itemIds = useMemo(
    () =>
      subPath
        .replace(/^\/+|\/+$/g, '')
        .split('/')
        .filter(Boolean),
    [subPath]
  );

  useEffect(() => {
    let cancelled = false;

    const resolveItem = async () => {
      setLoading(true);

      if (itemIds.length === 0) {
        if (!cancelled) {
          setItem(null);
          setLoading(false);
        }
        return;
      }

      let currentCase = _case;

      // Walk through all but the last ID, resolving nested cases
      for (let i = 0; i < itemIds.length - 1; i++) {
        const segmentId = itemIds[i];
        const matched = currentCase?.items?.find(
          _item => _item.id === segmentId && _item.type?.toLowerCase() === 'case'
        );

        if (!matched?.value) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }

        const nextCase = await dispatchApi(api.v2.case.get(matched.value), { throwError: false });
        if (!nextCase) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }
        currentCase = nextCase;
      }

      // Resolve the final item ID
      const finalId = itemIds[itemIds.length - 1];
      const resolvedItem = currentCase?.items?.find(_item => _item.id === finalId);

      if (!cancelled) {
        setItem(resolvedItem || null);
        setLoading(false);
      }
    };

    resolveItem();

    return () => {
      cancelled = true;
    };
  }, [_case, dispatchApi, itemIds]);

  if (loading) {
    return null;
  }

  if (!item) {
    return <NotFoundPage />;
  }

  if (item.type === 'hit' || item.type === 'event') {
    return <InformationPane selected={item.value} />;
  }

  if (item.type === 'case') {
    return <CaseDashboard caseId={item.value} />;
  }

  return <h1>{JSON.stringify(item)}</h1>;
};

export default ItemPage;

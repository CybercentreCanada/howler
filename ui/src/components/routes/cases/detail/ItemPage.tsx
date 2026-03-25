import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import NotFoundPage from 'components/routes/404';
import InformationPane from 'components/routes/hits/search/InformationPane';
import ObservableViewer from 'components/routes/observables/ObservableViewer';
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
  // When rendered directly with a case prop, fall back to parsing the pathname.
  const subPath = params['*'] ?? '';

  const normalizedSubPath = useMemo(() => subPath.replace(/^\/+|\/+$/g, ''), [subPath]);

  useEffect(() => {
    let cancelled = false;

    const resolveItem = async () => {
      setLoading(true);

      if (!normalizedSubPath) {
        if (!cancelled) {
          setItem(null);
          setLoading(false);
        }
        return;
      }

      let currentCase = _case;
      let remainingPath = normalizedSubPath;

      while (currentCase && remainingPath) {
        const currentRemainingPath = remainingPath;

        const matchedNestedCase = currentCase.items
          .filter(
            _item =>
              _item?.path &&
              _item?.type?.toLowerCase() === 'case' &&
              (currentRemainingPath === _item.path || currentRemainingPath.startsWith(`${_item.path}/`))
          )
          .sort((a, b) => (b.path?.length || 0) - (a.path?.length || 0))[0];

        if (!matchedNestedCase) {
          break;
        }

        if (currentRemainingPath === matchedNestedCase.path) {
          if (!cancelled) {
            setItem(matchedNestedCase);
            setLoading(false);
          }
          return;
        }

        if (!matchedNestedCase.id) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }

        const nextCase = await dispatchApi(api.v2.case.get(matchedNestedCase.id), { throwError: false });

        if (!nextCase) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }

        remainingPath = currentRemainingPath.slice((matchedNestedCase.path?.length || 0) + 1);
        currentCase = nextCase;
      }

      const resolvedItem = currentCase?.items?.find(_item => _item.path === remainingPath);

      if (!cancelled) {
        setItem(resolvedItem || null);
        setLoading(false);
      }
    };

    resolveItem();

    return () => {
      cancelled = true;
    };
  }, [_case, dispatchApi, normalizedSubPath]);

  if (loading) {
    return null;
  }

  if (!item) {
    return <NotFoundPage />;
  }

  if (item.type === 'hit') {
    return <InformationPane selected={item.id} />;
  }

  if (item.type === 'observable') {
    return <ObservableViewer observableId={item.id} />;
  }

  if (item.type === 'case') {
    return <CaseDashboard caseId={item.id} />;
  }

  return <h1>{JSON.stringify(item)}</h1>;
};

export default ItemPage;

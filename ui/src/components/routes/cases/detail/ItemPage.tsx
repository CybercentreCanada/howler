import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import NotFoundPage from 'components/routes/404';
import InformationPane from 'components/routes/hits/search/InformationPane';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useEffect, useMemo, useState, type FC } from 'react';
import { useOutletContext, useParams } from 'react-router-dom';
import useCase from '../hooks/useCase';
import { buildPathFromID } from '../utils';
import CaseDashboard from './CaseDashboard';
import MarkdownPage from './MarkdownPage';

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
          .filter(Boolean)
          .find(_item => _item.type === 'case' && currentRemainingPath.startsWith(`${_item.name}/`));

        if (!matchedNestedCase) {
          break;
        }

        if (currentRemainingPath === matchedNestedCase.id) {
          if (!cancelled) {
            setItem(matchedNestedCase);
            setLoading(false);
          }
          return;
        }

        if (!matchedNestedCase.value) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }

        const nextCase = await dispatchApi(api.v2.case.get(matchedNestedCase.value), { throwError: false });

        if (!nextCase) {
          if (!cancelled) {
            setItem(null);
            setLoading(false);
          }
          return;
        }

        remainingPath = currentRemainingPath.replace(`${matchedNestedCase.name}/`, '');
        currentCase = nextCase;
      }

      const resolvedItem = currentCase.items.find(_item => buildPathFromID(currentCase, _item.id) === remainingPath);

      if (!cancelled) {
        setItem(resolvedItem || null);
        setLoading(false);
      }
    };

    if (_case) {
      resolveItem();
    }

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

  if (item.type === 'hit' || item.type === 'event') {
    return <InformationPane selected={item.value} />;
  }

  if (item.type === 'case') {
    return <CaseDashboard caseId={item.value} />;
  }

  if (item.type === 'markdown') {
    return <MarkdownPage case={_case} item={item} />;
  }

  return <h1>{JSON.stringify(item)}</h1>;
};

export default ItemPage;

import NotFoundPage from 'components/routes/404';
import InformationPane from 'components/routes/hits/search/InformationPane';
import type { Case } from 'models/entities/generated/Case';
import { useMemo, type FC } from 'react';
import { useLocation } from 'react-router';

const ItemPage: FC<{ case: Case }> = ({ case: _case }) => {
  const location = useLocation();

  const subPath = decodeURIComponent(location.pathname).replace(`/cases/${_case.case_id}/`, '');

  const item = useMemo(() => _case.items.find(_item => _item.path === subPath), [_case.items, subPath]);

  if (!item) {
    return <NotFoundPage />;
  }

  if (item.type === 'hit') {
    return <InformationPane selected={item.id} />;
  }

  return <h1>{item.path}</h1>;
};

export default ItemPage;

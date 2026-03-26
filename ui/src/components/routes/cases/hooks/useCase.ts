import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, useEffect, useState } from 'react';

interface CaseArguments {
  case?: Case;
  caseId?: string;
}

interface CaseResult {
  case: Case;
  update: (update: Partial<Case>, publish?: boolean) => Promise<void>;
  loading: boolean;
  missing: boolean;
}

const useCase: (args: CaseArguments) => CaseResult = ({ caseId, case: providedCase }) => {
  const { dispatchApi } = useMyApi();

  const [loading, setLoading] = useState(false);
  const [missing, setMissing] = useState(false);
  const [_case, setCase] = useState(providedCase);

  useEffect(() => {
    if (providedCase) {
      setCase(providedCase);
    }
  }, [providedCase]);

  useEffect(() => {
    if (caseId) {
      setLoading(true);
      dispatchApi(api.v2.case.get(caseId), { throwError: false })
        .then(setCase)
        .finally(() => setLoading(false));
    }
  }, [caseId, dispatchApi]);

  const update = useCallback(
    async (_updatedCase: Partial<Case>, publish = true) => {
      if (!_case?.case_id) {
        return;
      }

      try {
        if (publish) {
          setCase(await dispatchApi(api.v2.case.put(_case.case_id, _updatedCase)));
        } else {
          setCase(_updatedCase);
        }
      } catch (e) {
        setMissing(true);
      } finally {
        return;
      }
    },
    [_case?.case_id, dispatchApi]
  );

  return { case: _case, update, loading, missing };
};

export default useCase;

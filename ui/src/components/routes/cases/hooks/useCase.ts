import api from 'api';
import { SocketContext } from 'components/app/providers/SocketProvider';
import useMyApi from 'components/hooks/useMyApi';
import type { Case } from 'models/entities/generated/Case';
import { useCallback, useContext, useEffect, useState } from 'react';
import { isCaseUpdate } from 'utils/socketUtils';

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
  const { addListener, removeListener } = useContext(SocketContext);

  const [loading, setLoading] = useState(false);
  const [missing, setMissing] = useState(false);
  const [_case, setCase] = useState(providedCase);

  const activeCaseId = _case?.case_id ?? caseId;

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

  useEffect(() => {
    if (!activeCaseId) {
      return;
    }

    const listenerKey = `case-update-${activeCaseId}`;
    addListener(listenerKey, data => {
      if (isCaseUpdate(data) && data.case.case_id === activeCaseId) {
        setCase(data.case);
      }
    });

    return () => {
      removeListener(listenerKey);
    };
  }, [activeCaseId, addListener, removeListener]);

  const update = useCallback(
    async (_updatedCase: Partial<Case>, publish = true) => {
      if (!activeCaseId) {
        return;
      }

      try {
        if (publish) {
          setCase(await dispatchApi(api.v2.case.put(activeCaseId, _updatedCase)));
        } else {
          setCase(prevCase => {
            if (!prevCase) {
              return prevCase;
            }

            return {
              ...prevCase,
              ..._updatedCase
            };
          });
        }
      } catch (e) {
        setMissing(true);
      } finally {
        return;
      }
    },
    [activeCaseId, dispatchApi]
  );

  return { case: _case, update, loading, missing };
};

export default useCase;

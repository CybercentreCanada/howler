import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import useMyApi from 'components/hooks/useMyApi';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useState, type FC, type PropsWithChildren } from 'react';
import { createContext, useContextSelector } from 'use-context-selector';

export interface DossierContextType {
  ready: boolean;
  dossiers: Dossier[];
  fetchDossiers: (force?: boolean) => Promise<void>;
  addDossier: (v: Dossier) => Promise<Dossier>;
  editDossier: (dossier: Dossier) => Promise<Dossier>;
  removeDossier: (id: string) => Promise<void>;
  getCurrentDossiers: () => Dossier[];
  getMatchingDossiers: (id: string) => Promise<Dossier[]>;
}

export const DossierContext = createContext<DossierContextType>(null);

const DossierProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();
  const appUser = useAppUser<HowlerUser>();

  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [dossiers, setDossiers] = useState<Dossier[]>([]);
  const [idToDossiers, setIdToDossiers] = useState<Record<string, Dossier[]>>({});

  const fetchDossiers = useCallback(
    async (force = false) => {
      if (ready && !force) {
        return;
      }

      if (!appUser.isReady()) {
        return;
      }

      setLoading(true);
      try {
        setDossiers((await api.dossier.get()) as Dossier[]);
        setReady(true);
      } finally {
        setLoading(false);
      }
    },
    [appUser, ready]
  );

  useEffect(() => {
    if (!ready && !loading) {
      fetchDossiers();
    }
  }, [fetchDossiers, ready, loading]);

  const getCurrentDossiers = useCallback(() => {
    return [];
  }, []);

  const editDossier = useCallback(async (dossier: Dossier) => {
    const result = await api.dossier.put(dossier.dossier_id, dossier);

    setDossiers(_dossiers =>
      _dossiers.map(_dossier => (_dossier.dossier_id === dossier.dossier_id ? { ..._dossier, dossier } : _dossier))
    );

    return result;
  }, []);

  const addDossier = useCallback(
    async (dossier: Dossier) => {
      const newDossier = await dispatchApi(api.dossier.post(dossier));

      setDossiers(_dossiers => [..._dossiers, newDossier]);

      return newDossier;
    },
    [dispatchApi]
  );

  const removeDossier = useCallback(async (id: string) => {
    const result = await api.dossier.del(id);

    setDossiers(_dossiers => _dossiers.filter(v => v.dossier_id !== id));

    return result;
  }, []);

  const getMatchingDossiers = useCallback(
    async (id: string) => {
      if (idToDossiers[id]) {
        return idToDossiers[id];
      }

      const result = await dispatchApi(api.dossier.hit.get(id), { throwError: false });

      if (result) {
        setIdToDossiers(_dossiers => ({
          ..._dossiers,
          [id]: result
        }));

        return result;
      }

      return [];
    },
    [dispatchApi, idToDossiers]
  );

  return (
    <DossierContext.Provider
      value={{
        ready,
        dossiers,
        fetchDossiers,
        addDossier,
        editDossier,
        removeDossier,
        getCurrentDossiers,
        getMatchingDossiers
      }}
    >
      {children}
    </DossierContext.Provider>
  );
};

export const useDossierContextSelector = <Selected,>(selector: (value: DossierContextType) => Selected): Selected => {
  return useContextSelector<DossierContextType, Selected>(DossierContext, selector);
};

export default DossierProvider;

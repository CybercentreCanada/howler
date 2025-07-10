import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import { has } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { WithMetadata } from 'models/WithMetadata';
import { useCallback } from 'react';
import { useContextSelector } from 'use-context-selector';
import { HitContext } from '../providers/HitProvider';

const useMatchers = () => {
  const { dispatchApi } = useMyApi();
  const getHit = useContextSelector(HitContext, ctx => ctx.getHit);

  const getMatchingTemplate = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (has(hit, '__template')) {
        return hit.__template;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      return (await dispatchApi(api.hit.get<WithMetadata<Hit>>(hit.howler.id, ['template']))).__template;
    },
    [dispatchApi]
  );

  const getMatchingOverview = useCallback(
    async (hit: WithMetadata<Hit>) => {
      if (has(hit, '__overview')) {
        return hit.__overview;
      }

      // This is a fallback in case metadata is not included. In most cases templates are shown, the template metadata
      // should also exist
      return (await getHit(hit.howler.id, true)).__overview;
    },
    [getHit]
  );

  return {
    getMatchingOverview,
    getMatchingTemplate
  };
};

export default useMatchers;

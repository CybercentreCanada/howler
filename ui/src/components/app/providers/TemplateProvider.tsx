import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { FC, PropsWithChildren } from 'react';
import { useCallback, useRef, useState } from 'react';
import { createContext } from 'use-context-selector';

interface TemplateContextType {
  templates: Template[];
  getTemplates: (force?: boolean) => Promise<Template[]>;
  getMatchingTemplate: (h: Hit) => Template;
  refresh: () => void;
  loaded: boolean;
}

const SIX_TAIL_PHISH_DETAILS = [
  'event.start',
  'event.end',
  'destination.ip',
  'destination.domain',
  'cloud.service.name',
  'error.code',
  'error.message'
];

/**
 * TODO: Ask analysts to move these into the API
 */
const BUILTIN_TEMPLATES: Template[] = [
  {
    analytic: '6TailPhish',
    keys: SIX_TAIL_PHISH_DETAILS,
    owner: 'none',
    template_id: '6tailphish.builtin',
    type: 'readonly'
  }
];

export const TemplateContext = createContext<TemplateContextType>(null);

const TemplateProvider: FC<PropsWithChildren> = ({ children }) => {
  const request = useRef<Promise<Template[]>>(null);
  const { dispatchApi } = useMyApi();

  const [loaded, setLoaded] = useState(false);

  const templateRequest = useRef<Promise<Template[]>>(null);

  const [templates, setTemplates] = useState<Template[]>(BUILTIN_TEMPLATES);

  const getTemplates = useCallback(
    async (force = false) => {
      if (request.current) {
        return request.current;
      }

      if (loaded && !force) {
        return templates;
      } else if (templateRequest.current) {
        return templateRequest.current;
      } else {
        try {
          request.current = dispatchApi(api.template.get());

          const result = await request.current;
          const fullList = [...BUILTIN_TEMPLATES, ...result];

          setTemplates(fullList);
          setLoaded(true);

          return fullList;
        } catch (e) {
          return [];
        } finally {
          request.current = null;
        }
      }
    },
    [dispatchApi, loaded, templates]
  );

  /**
   * Based on a given hit, retrieve the best match for a template
   */
  const getMatchingTemplate = useCallback(
    (hit: Hit) =>
      templates
        .filter(
          _template =>
            // The analytic must match, and the detection must either a) not exist or b) match the hit
            _template.analytic === hit.howler.analytic &&
            (!_template.detection || _template.detection.toLowerCase() === hit.howler.detection?.toLowerCase())
        )
        .sort((a, b) => {
          // Sort priority:
          // 1. personal > readonly > global
          // 2. detection > !detection

          if (a.type !== b.type) {
            const order = {
              personal: 2,
              readonly: 1,
              global: 0
            };

            return order[b.type] - order[a.type];
          } else {
            if (a.detection && !b.detection) {
              return -1;
            } else if (!a.detection && b.detection) {
              return 1;
            } else {
              return 0;
            }
          }
        })[0],
    [templates]
  );

  const refresh = useCallback(() => {
    setLoaded(false);
    getTemplates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <TemplateContext.Provider value={{ templates, getTemplates, getMatchingTemplate, refresh, loaded }}>
      {children}
    </TemplateContext.Provider>
  );
};

export default TemplateProvider;

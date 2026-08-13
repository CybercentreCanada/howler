import { ContentPaste, FilterList, Info, Language, Lock, Person, type SvgIconComponent } from '@mui/icons-material';
import { IconButton, Stack, Tooltip, Typography, useTheme } from '@mui/material';
import useMatchers from 'components/app/hooks/useMatchers';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import get from 'lodash-es/get';
import isNil from 'lodash-es/isNil';
import isObject from 'lodash-es/isObject';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { WithMetadata } from 'models/WithMetadata';
import type { FC } from 'react';
import { memo, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { PROVIDER_COLORS, StorageKey } from 'utils/constants';
import { stringToColor } from 'utils/utils';
import PluginTypography from '../PluginTypography';
import { HitLayout } from './HitLayout';

export const DEFAULT_FIELDS = ['event.created', 'howler.id', 'howler.hash'];

const EditIcon: FC<{ label: string; icon: SvgIconComponent; link: string }> = ({ label, icon: Icon, link }) => (
  <Tooltip title={label}>
    <IconButton size="small" component={Link} to={link} aria-label={label}>
      <Icon sx={{ height: '16px !important', width: '16px !important' }} />
    </IconButton>
  </Tooltip>
);

const HitOutline: FC<{
  hit: WithMetadata<Hit>;
  lazy?: boolean;
  layout: HitLayout;
  forceAllFields?: boolean;
  template?: Template;
}> = ({ hit, layout, lazy = false, forceAllFields = false, template: providedTemplate = null }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const addFilter = useContextSelector(ParameterContext, ctx => ctx?.addFilter);
  const { getMatchingTemplate } = useMatchers(lazy);

  const [templateFieldCount] = useMyLocalStorageItem(StorageKey.TEMPLATE_FIELD_COUNT, null);
  const [template, setTemplate] = useState<Template>(null);

  const providerColor = useMemo(() => {
    if (!hit?.event.provider) {
      return PROVIDER_COLORS.unknown;
    }

    return PROVIDER_COLORS[hit?.event.provider] ?? stringToColor(hit?.event.provider);
  }, [hit?.event.provider]);

  const fields = useMemo(() => {
    const keys = template?.keys;

    if (!keys?.length) {
      return DEFAULT_FIELDS;
    }

    if (!isNil(templateFieldCount) && !forceAllFields) {
      return keys.slice(0, templateFieldCount);
    }

    return keys;
  }, [template, templateFieldCount, forceAllFields]);

  const editUrl = useMemo(() => {
    const params: { [index: string]: string } = {
      analytic: hit.howler.analytic,
      type: template?.type ?? 'personal'
    };

    if (template?.detection) {
      params.detection = template.detection;
    } else if (!template && hit.howler.detection) {
      params.detection = hit.howler.detection;
    }

    return '/templates/view?' + new URLSearchParams(params).toString();
  }, [template, hit]);

  useEffect(() => {
    void getMatchingTemplate(hit, providedTemplate).then(setTemplate);
  }, [getMatchingTemplate, hit, providedTemplate]);

  if (fields.length < 1) {
    return null;
  }

  return (
    <Stack sx={{ my: 1, borderLeft: `5px solid ${providerColor}`, pl: 1, alignItems: 'stretch' }}>
      <Stack direction="row" spacing={0.5} alignItems="center">
        <Typography variant="body2" fontWeight="bold">
          {t('hit.details.title')}
        </Typography>
        {template?.type === 'readonly' ? (
          <EditIcon label={t('route.templates.builtin')} icon={Lock} link={editUrl} />
        ) : !template ? (
          <EditIcon label={t('route.templates.default')} icon={Info} link={editUrl} />
        ) : template.type === 'global' ? (
          <EditIcon label={t('route.templates.global')} icon={Language} link={editUrl} />
        ) : (
          <EditIcon label={t('route.templates.personal')} icon={Person} link={editUrl} />
        )}
      </Stack>
      {(fields ?? [])
        .map<[string, string]>(field => [field, get(hit, field)])
        .map(([field, data]) => {
          const displayedData: string = (
            Array.isArray(data) ? data.join(', ') : isObject(data) ? JSON.stringify(data) : data
          )?.toString();

          if (!displayedData) {
            return null;
          }

          return (
            <Stack
              direction="row"
              key={field}
              spacing={1}
              sx={{
                '& .copy': { opacity: 0, cursor: 'pointer', transition: theme.transitions.create('opacity') },
                '&:hover .copy': { opacity: 1 },
                position: 'relative',
                pr: '75px'
              }}
            >
              <Tooltip title={(config.indexes.hit[field]?.description ?? t('none')).split('\n')[0]}>
                <Typography variant={layout !== HitLayout.COMFY ? 'caption' : 'body1'} fontWeight="bold">
                  {field}:
                </Typography>
              </Tooltip>
              <PluginTypography
                context="outline"
                variant={layout !== HitLayout.COMFY ? 'caption' : 'body1'}
                whiteSpace="normal"
                sx={{ wordBreak: 'break-all' }}
                value={displayedData}
                field={field}
                obj={hit}
              >
                {displayedData}
              </PluginTypography>
              <Stack
                spacing={0.25}
                direction="row"
                sx={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)' }}
              >
                <Tooltip title={t('hit.outline.copy')}>
                  <IconButton
                    className="copy"
                    size="small"
                    onClick={e => {
                      e.preventDefault();
                      e.stopPropagation();
                      void navigator.clipboard.writeText(displayedData);
                    }}
                  >
                    <ContentPaste fontSize="small" />
                  </IconButton>
                </Tooltip>

                {addFilter && (
                  <Tooltip title={t('hit.outline.add_filter')}>
                    <IconButton
                      className="copy"
                      size="small"
                      onClick={e => {
                        e.preventDefault();
                        e.stopPropagation();
                        addFilter(`${field}:"${displayedData}"`);
                      }}
                    >
                      <FilterList fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
            </Stack>
          );
        })}
    </Stack>
  );
};

export default memo(HitOutline);

import { Info, Language, Lock, Person } from '@mui/icons-material';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import PluginTypography from 'components/elements/PluginTypography';
import { get, isObject } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import type { FC } from 'react';
import React, { memo, useCallback, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { HitLayout } from '../HitLayout';

const DefaultOutline: FC<{
  hit: Hit;
  fields: string[];
  template?: Template;
  layout?: HitLayout;
  readonly?: boolean;
}> = ({ hit, fields, template, layout = HitLayout.NORMAL, readonly = false }) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const navigate = useNavigate();

  const handleOpen = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();

      const params: { [index: string]: string } = {
        analytic: hit.howler.analytic,
        type: template?.type ?? 'personal'
      };

      if (template?.detection) {
        params.detection = template.detection;
      } else if (!template && hit.howler.detection) {
        params.detection = hit.howler.detection;
      }

      navigate(
        '/templates/view?' +
          Object.entries(params)
            .map(([key, val]) => `${key}=${val}`)
            .join('&')
      );
    },
    [hit.howler.analytic, hit.howler.detection, navigate, template]
  );

  return (
    <Box display="grid" gridTemplateColumns="auto 1fr" columnGap={1} sx={{ position: 'relative' }}>
      <IconButton size="small" sx={{ position: 'absolute', right: 0, top: 0 }} onClick={handleOpen}>
        {readonly ? ( // Built in template
          <Tooltip title={t('route.templates.builtin')}>
            <Lock fontSize="small" />
          </Tooltip>
        ) : !template ? ( // No type specified => using the default
          <Tooltip title={t('route.templates.default')}>
            <Info fontSize="small" />
          </Tooltip>
        ) : template.type === 'global' ? ( // Type is global => global template
          <Tooltip title={t('route.templates.global')}>
            <Language fontSize="small" />
          </Tooltip>
        ) : (
          // Finally, type isn't global => personal template
          <Tooltip title={t('route.templates.personal')}>
            <Person fontSize="small" />
          </Tooltip>
        )}
      </IconButton>
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
            <React.Fragment key={field}>
              <Tooltip title={(config.indexes.hit[field]?.description ?? t('none')).split('\n')[0]}>
                <Typography variant={layout !== HitLayout.COMFY ? 'caption' : 'body1'} fontWeight="bold">
                  {field}:
                </Typography>
              </Tooltip>
              <PluginTypography
                context="outline"
                variant={layout !== HitLayout.COMFY ? 'caption' : 'body1'}
                whiteSpace="normal"
                sx={{ width: '100%', wordBreak: 'break-all' }}
                value={displayedData}
                field={field}
                hit={hit}
              >
                {displayedData}
              </PluginTypography>
            </React.Fragment>
          );
        })}
    </Box>
  );
};

export default memo(DefaultOutline);

import { Article } from '@mui/icons-material';
import { Box, Fab, Skeleton, Stack, Typography, useMediaQuery } from '@mui/material';
import 'chartjs-adapter-moment';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { TemplateContext } from 'components/app/providers/TemplateProvider';
import type { Analytic } from 'models/entities/generated/Analytic';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import TemplateCard from '../templates/TemplateCard';

const AnalyticTemplates: FC<{ analytic: Analytic }> = ({ analytic }) => {
  const { t } = useTranslation();
  const isNarrow = useMediaQuery('(max-width: 1800px)');

  const getTemplates = useContextSelector(TemplateContext, ctx => ctx.getTemplates);
  const templates = useContextSelector(TemplateContext, ctx =>
    ctx.templates.filter(_template => _template.analytic === analytic?.name)
  );

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getTemplates().finally(() => setLoading(false));
  }, [getTemplates]);

  if (!analytic) {
    return <Skeleton variant="rounded" width="100%" sx={{ minHeight: '300px', mt: 2 }} />;
  }

  return (
    <Stack spacing={1} position="relative">
      <Fab
        component={Link}
        to={`/templates/view?analytic=${analytic.name}`}
        variant="extended"
        size="large"
        color="primary"
        sx={theme => ({
          textTransform: 'none',
          position: isNarrow ? 'fixed' : 'absolute',
          right: isNarrow ? theme.spacing(2) : `calc(100% + ${theme.spacing(5)})`,
          whiteSpace: 'nowrap',
          ...(isNarrow ? { bottom: theme.spacing(1) } : { top: theme.spacing(2) })
        })}
      >
        <Article sx={{ mr: 1 }} />
        <Typography>{t('route.templates.create')}</Typography>
      </Fab>
      {loading && <Skeleton width="100%" height="175px" />}
      {!loading && templates.length < 1 && <AppListEmpty />}
      {templates.map(template => (
        <Box
          component={Link}
          to={`/templates/view?analytic=${template.analytic}${template.detection ? '&template=' + template.detection : ''}&type=${template.type}`}
          key={template.template_id}
          sx={theme => ({
            textDecoration: 'none',
            '& > .MuiCard-root': {
              cursor: 'pointer',
              transition: theme.transitions.create('border-color'),
              '&:hover': { borderColor: 'primary.main' }
            }
          })}
        >
          <TemplateCard template={template} />
        </Box>
      ))}
    </Stack>
  );
};

export default AnalyticTemplates;

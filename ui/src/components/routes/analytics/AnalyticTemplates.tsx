import { Article } from '@mui/icons-material';
import { Box, Fab, Skeleton, Stack, Typography, useMediaQuery } from '@mui/material';
import api from 'api';
import 'chartjs-adapter-dayjs-4';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import useMyApi from 'components/hooks/useMyApi';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Template } from 'models/entities/generated/Template';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import TemplateCard from '../templates/TemplateCard';

const AnalyticTemplates: FC<{ analytic: Analytic }> = ({ analytic }) => {
  const { t } = useTranslation();
  const isNarrow = useMediaQuery('(max-width: 1800px)');
  const { dispatchApi } = useMyApi();

  const [templates, setTemplates] = useState<Template[]>([]);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    dispatchApi(api.template.get())
      .then(_templates => _templates.filter(_template => _template.analytic === analytic?.name))
      .then(setTemplates)
      .finally(() => setLoading(false));
  }, [analytic?.name, dispatchApi]);

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

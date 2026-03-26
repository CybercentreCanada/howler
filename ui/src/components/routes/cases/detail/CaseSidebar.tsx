import { Circle, Dashboard, Dataset } from '@mui/icons-material';
import { alpha, Box, Card, Chip, Divider, Skeleton, Stack, Typography, useTheme } from '@mui/material';
import dayjs from 'dayjs';
import type { Case } from 'models/entities/generated/Case';
import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { ESCALATION_COLOR_MAP } from '../constants';
import CaseFolder from './sidebar/CaseFolder';

interface CaseFolderProps {
  case: Case;
  update: (newCase: Case) => void;
}

const CaseSidebar: FC<CaseFolderProps> = ({ case: _case, update }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const theme = useTheme();

  return (
    <Box
      sx={{
        flex: 1,
        maxWidth: '350px',
        maxHeight: 'calc(100vh - 64px)',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Card sx={{ borderRadius: 0, px: 2, py: 1 }}>
        {_case?.title ? <Typography variant="body1">{_case.title}</Typography> : <Skeleton height={24} />}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          divider={<Circle color="disabled" sx={{ fontSize: '8px' }} />}
        >
          <Typography variant="caption" color="textSecondary">
            {t('started')}: {_case?.created ? dayjs(_case.created).toString() : <Skeleton height={14} />}
          </Typography>
          {_case?.escalation ? (
            <Chip color={ESCALATION_COLOR_MAP[_case.escalation]} label={t(_case.escalation)} />
          ) : (
            <Skeleton height={24} />
          )}
        </Stack>
      </Card>

      <Stack
        direction="row"
        alignItems="center"
        sx={[
          {
            cursor: 'pointer',
            px: 1,
            py: 1,
            transition: theme.transitions.create('background', { duration: 100 }),
            color: `${theme.palette.text.primary} !important`,
            textDecoration: 'none',
            background: 'transparent',
            borderRight: `thin solid ${theme.palette.divider}`,
            '&:hover': {
              background: alpha(theme.palette.grey[600], 0.25)
            }
          },
          location.pathname === `/cases/${_case?.case_id}` && {
            background: alpha(theme.palette.grey[600], 0.15),
            borderRight: `3px solid ${theme.palette.primary.main}`
          }
        ]}
        component={Link}
        to={`/cases/${_case?.case_id}`}
      >
        <Dashboard />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.dashboard')}</Typography>
      </Stack>

      <Stack
        direction="row"
        alignItems="center"
        sx={[
          {
            cursor: 'pointer',
            px: 1,
            py: 1,
            transition: theme.transitions.create('background', { duration: 100 }),
            color: `${theme.palette.text.primary} !important`,
            textDecoration: 'none',
            background: 'transparent',
            borderRight: `thin solid ${theme.palette.divider}`,
            '&:hover': {
              background: alpha(theme.palette.grey[600], 0.25)
            }
          },
          location.pathname === `/cases/${_case?.case_id}/assets` && {
            background: alpha(theme.palette.grey[600], 0.15),
            borderRight: `3px solid ${theme.palette.primary.main}`
          }
        ]}
        component={Link}
        to={`/cases/${_case?.case_id}/assets`}
      >
        <Dataset />
        <Typography sx={{ userSelect: 'none', pl: 0.5, textWrap: 'nowrap' }}>{t('page.cases.assets')}</Typography>
      </Stack>

      <Divider />

      {_case && (
        <Box
          flex={1}
          overflow="auto"
          width="100%"
          sx={{
            position: 'relative',
            borderRight: `thin solid ${theme.palette.divider}`
          }}
        >
          <Box position="absolute" sx={{ left: 0, right: 0 }}>
            <CaseFolder case={_case} onItemRemoved={update} />
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default CaseSidebar;

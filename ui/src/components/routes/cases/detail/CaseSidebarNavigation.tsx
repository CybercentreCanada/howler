import { CalendarMonth, Dashboard, Dataset, Rule, Search } from '@mui/icons-material';
import { alpha, Stack, Typography, useTheme } from '@mui/material';
import type { FC } from 'react';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

const NAV_ITEMS = [
  { id: 'dashboard', Icon: Dashboard, label: 'page.cases.dashboard', path: '', fontSize: 'small' },
  { id: 'search', Icon: Search, label: 'page.cases.search', path: 'search', fontSize: 'small' },
  { id: 'observables', Icon: Dataset, label: 'page.cases.observables', path: 'observables', fontSize: 'small' },
  { id: 'timeline', Icon: CalendarMonth, label: 'page.cases.timeline', path: 'timeline', fontSize: 'small' },
  { id: 'rules', Icon: Rule, label: 'page.cases.rules', path: 'rules', fontSize: 'medium' }
] as const;

export type CaseNavigationSection = (typeof NAV_ITEMS)[number]['id'];

interface CaseSidebarNavigationProps {
  caseId?: string;
  sections?: CaseNavigationSection[];
}

const CaseSidebarNavigation: FC<CaseSidebarNavigationProps> = ({
  caseId,
  sections = NAV_ITEMS.map(item => item.id)
}) => {
  const { t } = useTranslation();
  const location = useLocation();
  const theme = useTheme();

  const navItemSx = useCallback(
    (isActive: boolean) => [
      {
        cursor: caseId ? 'pointer' : 'default',
        px: 0.5,
        py: 0.5,
        transition: theme.transitions.create('background', { duration: 100 }),
        color: `${theme.palette.text.primary} !important`,
        textDecoration: 'none',
        background: 'transparent',
        borderRight: `thin solid ${theme.palette.divider}`,
        '&:hover': {
          background: alpha(theme.palette.grey[600], 0.25)
        }
      },
      isActive && {
        background: alpha(theme.palette.grey[600], 0.15),
        borderRight: `3px solid ${theme.palette.primary.main}`
      }
    ],
    [caseId, theme]
  );

  return (
    <Stack>
      {NAV_ITEMS.filter(item => sections.includes(item.id)).map(({ id, Icon, label, path, fontSize }) => {
        const active = !!caseId && (path ? location.pathname.endsWith(path) : location.pathname.endsWith(caseId));
        const child = (
          <>
            <Icon fontSize={fontSize} />
            <Typography
              variant="body2"
              sx={{ pl: 1, textWrap: 'nowrap', ...(id !== 'dashboard' && { userSelect: 'none' }) }}
            >
              {t(label)}
            </Typography>
          </>
        );
        const sx = navItemSx(active);

        return caseId ? (
          <Stack
            key={id}
            direction="row"
            alignItems="center"
            sx={sx}
            component={Link}
            to={`/cases/${caseId}${path ? `/${path}` : ''}`}
          >
            {child}
          </Stack>
        ) : (
          <Stack key={id} direction="row" alignItems="center" sx={sx}>
            {child}
          </Stack>
        );
      })}
    </Stack>
  );
};

export default CaseSidebarNavigation;

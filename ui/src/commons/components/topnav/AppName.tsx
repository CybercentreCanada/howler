import { Menu } from '@mui/icons-material';
import { IconButton, styled, useMediaQuery, useTheme } from '@mui/material';
import { useAppConfigs, useAppLeftNav, useAppLogo } from 'commons/components/app/hooks';
import { memo } from 'react';
import { Link } from 'react-router-dom';

const StyledTitle = styled('div')({
  display: 'flex',
  alignItems: 'center',
  flex: '0 0 auto',
  fontSize: '1.5rem',
  letterSpacing: '-1px'
});

const StyledIcon = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  padding: '0',
  minWidth: theme.spacing(7)
}));

const AppName = ({ noName }: { noName?: boolean }) => {
  const theme = useTheme();
  const logo = useAppLogo();
  const configs = useAppConfigs();
  const leftnav = useAppLeftNav();
  const isXs = useMediaQuery(theme.breakpoints.only('xs'));
  if (isXs) {
    return (
      <StyledTitle style={{ paddingLeft: theme.spacing(2) }}>
        <StyledIcon>
          <IconButton aria-label="open drawer" edge="start" onClick={leftnav.toggle} size="large" color="inherit">
            <Menu />
          </IconButton>
        </StyledIcon>
        <div>{!noName && configs.preferences.appName}</div>
      </StyledTitle>
    );
  }
  return (
    <Link
      to={configs.preferences.appLink}
      style={{ color: 'inherit', textDecoration: 'none', paddingLeft: theme.spacing(2) }}
    >
      <StyledTitle>
        <StyledIcon>{logo}</StyledIcon>
        <div>{!noName && configs.preferences.appName}</div>
      </StyledTitle>
    </Link>
  );
};

export default memo(AppName);

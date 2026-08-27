import { Box, Container, Stack, Typography, styled } from '@mui/material';
import { PageCardCentered, useAppLayout } from '@tui/core';
import { AppBrand } from 'branding/AppBrand';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const LogWrap = styled('div')(() => ({
  marginTop: '2rem',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center'
}));

const InjectCss = styled(Stack)(({ theme }) => ({
  '.login-stack': {
    marginTop: theme.spacing(2),
    marginBottom: theme.spacing(-4)
  },
  '.MuiPaper-root': {
    width: 'unset',
    maxWidth: 'unset'
  }
}));

const Logout: FC = () => {
  const { t } = useTranslation();
  const layout = useAppLayout();
  const localStorage = useMyLocalStorage();

  // hide topnav and leftnav on logout.
  layout.hideMenus();

  // There is probably more stuff to be done to properly logout a user.
  setTimeout(() => {
    localStorage.clear();
    window.location.replace('/');
  }, 2000);

  return (
    <Container component="main" maxWidth="xs">
      <InjectCss direction="column" alignItems="center">
        <PageCardCentered>
          <LogWrap>
            <AppBrand application="howler" variant="banner-vertical" size="large" />
            <Box m={2} />
            <Typography>{t('page.logout')}</Typography>
          </LogWrap>
        </PageCardCentered>
      </InjectCss>
    </Container>
  );
};

export default Logout;

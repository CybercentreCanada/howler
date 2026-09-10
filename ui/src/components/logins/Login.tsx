import { Box, CircularProgress, Container, Stack, styled } from '@mui/material';
import { PageCardCentered } from '@tui/core';
import { AppBrand } from 'branding/AppBrand';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import TextDivider from 'components/elements/display/TextDivider';
import { useContext } from 'react';
import OAuthLogin from './auth/OAuthLogin';
import UserPassLogin from './auth/UserPassLogin';

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

const LoginScreen = () => {
  const { config, loaded } = useContext(ApiConfigContext);

  return (
    <Container component="main" maxWidth="xs">
      <InjectCss direction="column" alignItems="center">
        <PageCardCentered>
          <LogWrap>
            <AppBrand application="howler" variant="banner-vertical" size="large" />
            <Box m={2} />
            {!loaded ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress />
              </div>
            ) : (
              <>
                {config.configuration?.auth?.internal?.enabled && (
                  <>
                    <UserPassLogin />
                    {!!config.configuration?.auth?.oauth_providers?.length && <TextDivider />}
                  </>
                )}
                {!!config.configuration?.auth?.oauth_providers?.length && (
                  <OAuthLogin providers={config.configuration?.auth?.oauth_providers} />
                )}
              </>
            )}
          </LogWrap>
        </PageCardCentered>
      </InjectCss>
    </Container>
  );
};

export default LoginScreen;

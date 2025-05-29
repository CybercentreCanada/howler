import { Box, CircularProgress, Container, Stack, styled } from '@mui/material';
import { useAppBanner } from 'commons/components/app/hooks';
import PageCardCentered from 'commons/components/pages/PageCardCentered';
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
  const banner = useAppBanner();
  const { config } = useContext(ApiConfigContext);
  const loading = config.configuration === null;

  return (
    <Container component="main" maxWidth="xs">
      <InjectCss direction="column" alignItems="center">
        <PageCardCentered>
          <LogWrap>
            {banner}
            <Box m={2} />
            {loading && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress />
              </div>
            )}
            {config.configuration?.auth?.internal?.enabled && (
              <>
                <UserPassLogin />
                {config.configuration?.auth?.oauth_providers?.length > 0 && <TextDivider />}
              </>
            )}

            {config.configuration?.auth?.oauth_providers?.length > 0 && (
              <OAuthLogin providers={config.configuration?.auth?.oauth_providers} />
            )}
          </LogWrap>
        </PageCardCentered>
      </InjectCss>
    </Container>
  );
};

export default LoginScreen;

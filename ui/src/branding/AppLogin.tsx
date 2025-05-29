import { Login } from '@mui/icons-material';
import { Box, Button, Stack, styled } from '@mui/material';
import PageCardCentered from 'commons/components/pages/PageCardCentered';
import type { BrandApplication } from './AppBrand';
import { AppBrand } from './AppBrand';

type BrandLoginVariant = 'card-centered' | 'inline';

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

const AppLoginInline = ({ application }: { application: BrandApplication }) => {
  return (
    <Stack className="login-stack" direction="column" alignItems="center" sx={{ minWidth: 300 }}>
      <AppBrand application={application} size="medium" variant="banner-vertical" />
      <Box m={2} />
      <Button endIcon={<Login />} variant="contained" fullWidth>
        {'Login'}
      </Button>
    </Stack>
  );
};

export const AppLogin = ({
  application,
  variant = 'card-centered'
}: {
  application: BrandApplication;
  variant?: BrandLoginVariant;
}) => {
  return variant === 'inline' ? (
    <AppLoginInline application={application} />
  ) : (
    <InjectCss direction="column" alignItems="center">
      <PageCardCentered>
        <AppLoginInline application={application} />
      </PageCardCentered>
    </InjectCss>
  );
};

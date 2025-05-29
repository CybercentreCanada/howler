import { Help } from '@mui/icons-material';
import {
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import api from 'api';
import type { HelpResponse } from 'api/help';
import { useAppUser } from 'commons/components/app/hooks';
import PageCenter from 'commons/components/pages/PageCenter';
import Markdown from 'components/elements/display/Markdown';
import useMyApi from 'components/hooks/useMyApi';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useEffect, useState, type FC } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Fragment } from 'react/jsx-runtime';

const APIKEY_LABELS = {
  R: 'apikey.read',
  W: 'apikey.write',
  E: 'apikey.extended',
  I: 'apikey.impersonate'
};

const ApiDocumentation: FC = () => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const { dispatchApi } = useMyApi();
  const theme = useTheme();
  useScrollRestoration();

  const isLg = useMediaQuery(theme.breakpoints.down('lg'));

  const [data, setData] = useState<HelpResponse>(null);

  useEffect(() => {
    dispatchApi(api.help.get()).then(setData);
  }, [dispatchApi]);

  if (!data) {
    return (
      <PageCenter margin={4} maxWidth="1750px" width="100%" textAlign="left">
        {t('loading')}
      </PageCenter>
    );
  }

  return (
    <PageCenter margin={4} maxWidth="1750px" width="100%" textAlign="left">
      <Stack spacing={2}>
        <Typography variant="h4">{t('page.documentation.categories')}</Typography>
        <TableContainer component={Paper}>
          <Table sx={{ '& td': { verticalAlign: 'top' }, '& tr:last-of-type > td': { border: 0 } }}>
            <TableHead>
              <TableRow>
                <TableCell>{t('page.documentation.categories.category')}</TableCell>
                <TableCell>{t('page.documentation.categories.description')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.keys(data.blueprints).map(key => (
                <TableRow key={key} sx={{ width: '100%' }}>
                  <TableCell>
                    <code>{key}</code>
                  </TableCell>
                  <TableCell>{data.blueprints[key]}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <Typography variant="h4" sx={{ pt: 4 }}>
          {t('page.documentation.endpoints')}
        </Typography>
        <TableContainer component={Paper}>
          <Table
            sx={{
              '& td': { verticalAlign: 'top' },
              '& tr:last-of-type > td': { border: 0 },
              '& pre': {
                backgroundColor: 'background.paper',
                padding: 0.75,
                borderRadius: '5px'
              },
              '& :not(pre) > code': {
                backgroundColor: 'background.paper',
                padding: 0.75,
                borderRadius: '5px'
              }
            }}
          >
            <TableHead>
              <TableRow>
                <Tooltip placement="top-start" title={<Trans i18nKey="page.documentation.endpoint.explanation" />}>
                  <TableCell>
                    {t('page.documentation.endpoint')}
                    <Help sx={{ height: '16px', width: '16px', ml: 1 }} />
                  </TableCell>
                </Tooltip>
                <Tooltip placement="top-start" title={<Trans i18nKey="page.documentation.required_type.explanation" />}>
                  <TableCell>
                    {t('page.documentation.required_type')}
                    <Help sx={{ height: '16px', width: '16px', ml: 1 }} />
                  </TableCell>
                </Tooltip>
                <Tooltip placement="top-start" title={<Trans i18nKey="page.documentation.required_priv.explanation" />}>
                  <TableCell>
                    {t('page.documentation.required_priv')}
                    <Help sx={{ height: '16px', width: '16px', ml: 1 }} />
                  </TableCell>
                </Tooltip>
                {!isLg && (
                  <Tooltip placement="top-start" title={<Trans i18nKey="page.documentation.description.explanation" />}>
                    <TableCell>
                      {t('page.documentation.description')}
                      <Help sx={{ height: '16px', width: '16px', ml: 1 }} />
                    </TableCell>
                  </Tooltip>
                )}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.apis.map(endpoint => {
                const documentationCell = (
                  <Markdown
                    md={endpoint.description
                      .replace(/(:\n)(None)/g, '$1\n`$2`')
                      .replace(/(\S+)\s+=>\s+(.+)/g, '\n`$1`: $2\n')
                      .replace(
                        /(Data Block:\n)([\s\S]+)(Result Example:)/,
                        (__, p1: string, p2: string, p3: string) => `${p1}\`\`\`\n${p2.trim()}\n\`\`\`\n${p3}`
                      )
                      .replace(
                        /(Result Example:\n)([\s\S]+)$/,
                        (__, p1: string, p2: string) => `${p1}\`\`\`\n${p2.trim()}\n\`\`\``
                      )}
                  />
                );

                return (
                  <Fragment key={endpoint.id}>
                    <TableRow style={{ marginBottom: '1rem' }} sx={[isLg && { '& > td': { borderBottom: 0 } }]}>
                      <TableCell>
                        <Stack direction="column" spacing={1} alignItems="start">
                          <Typography>{endpoint.name}</Typography>
                          <code>{endpoint.path}</code>
                          <Stack direction="row" spacing={1}>
                            {endpoint.complete ? (
                              <Chip size="small" label="Stable" color="success" />
                            ) : (
                              <Chip size="small" label="Unstable" color="error" />
                            )}
                            {endpoint.protected ? (
                              <Chip size="small" label="Protected" color="warning" />
                            ) : (
                              <Chip size="small" label="Unprotected" />
                            )}
                          </Stack>
                          <Stack spacing={1} direction="row">
                            {endpoint.methods.map(m => (
                              <Chip key={m} size="small" label={m} />
                            ))}
                          </Stack>
                          {endpoint.ui_only && <Chip size="small" label="UI Only" />}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={1} direction="row">
                          {endpoint.required_type.map(type => (
                            <Chip
                              key={type}
                              size="small"
                              label={type}
                              color={user.roles?.includes(type) ? 'success' : 'default'}
                            />
                          ))}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={1} direction="row">
                          {endpoint.required_priv.map((p: 'R' | 'W' | 'E' | 'I') => (
                            <Chip key={p} size="small" label={t(APIKEY_LABELS[p])} />
                          ))}
                        </Stack>
                      </TableCell>
                      {!isLg && <TableCell>{documentationCell}</TableCell>}
                    </TableRow>
                    {isLg && (
                      <TableRow>
                        <TableCell colSpan={3} sx={{ '& pre': { whiteSpace: 'pre-wrap' } }}>
                          {documentationCell}
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Stack>
    </PageCenter>
  );
};

export default ApiDocumentation;

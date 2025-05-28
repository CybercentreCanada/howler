import { Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const QueryResultText: FC<{ count: number; query: string }> = ({ count, query }) => {
  const { t } = useTranslation();

  return (
    <Typography
      sx={theme => ({
        color: theme.palette.text.secondary,
        fontSize: '0.9em',
        fontStyle: 'italic',
        mb: 0.5,
        '& a': { color: theme.palette.text.secondary }
      })}
      variant="body2"
    >
      {t('search.total', { count })} <Link to={`/hits?query=${encodeURIComponent(query)}`}>{t('search.open')}</Link>
    </Typography>
  );
};

export default QueryResultText;

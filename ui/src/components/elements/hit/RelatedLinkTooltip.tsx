import { Box, Link, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const RelatedLinkTooltip: FC<{ title: string; href: string }> = ({ title, href }) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ maxWidth: 300 }}>
      <Typography variant="subtitle2">{title}</Typography>

      <Box sx={{ mt: 1, wordBreak: 'break-all' }}>
        <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
          {href}
        </Link>
      </Box>

      <Box sx={{ mt: 2 }}>
        <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover">
          {t('hit.header.link')}
        </Link>
      </Box>
    </Box>
  );
};

export default RelatedLinkTooltip;

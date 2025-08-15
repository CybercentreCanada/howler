import { Stack, Typography } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import React, { type PropsWithChildren } from 'react';
import { Link } from 'react-router-dom';
import RelatedIcon from './RelatedIcon';

const RelatedLink: React.FC<PropsWithChildren<{ icon?: string; title?: string; href?: string; compact?: boolean }>> = ({
  icon,
  title,
  href,
  compact = false,
  children
}) => {
  return (
    <HowlerCard
      variant={compact ? 'outlined' : 'elevation'}
      key={href}
      onClick={() => window.open(href)}
      sx={[
        theme => ({
          cursor: 'pointer',
          backgroundColor: 'transparent',
          transition: theme.transitions.create(['border-color']),
          '&:hover': { borderColor: 'primary.main', '& a': { textDecoration: 'underline' } },
          '& > div': {
            height: '100%'
          },
          '& a': { textDecoration: 'none', color: 'text.primary' }
        }),
        !compact && { border: 'thin solid', borderColor: 'transparent' }
      ]}
    >
      <Stack direction="row" p={compact ? 0.5 : 1} spacing={1} alignItems="center">
        {children || <RelatedIcon icon={icon} title={title} href={href} compact={compact} />}
        <Typography component={Link} to={href} onClick={e => e.stopPropagation()}>
          {title ?? href}
        </Typography>
      </Stack>
    </HowlerCard>
  );
};

export default RelatedLink;

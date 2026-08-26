import { Box, ListItemText, Stack, Tooltip, Typography } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import RelatedLinkTooltip from 'components/elements/hit/RelatedLinkTooltip';
import React, { type PropsWithChildren } from 'react';
import { Link } from 'react-router-dom';
import RelatedIcon from './RelatedIcon';

const RelatedLink: React.FC<
  PropsWithChildren<{
    icon?: string;
    title?: string;
    href?: string;
    compact?: boolean;
    target?: string;
    rel?: string;
    tooltip?: React.ReactNode;
    // list-item rendering used inside dropdown menus: no card outline, details are shown inline instead of in a tooltip
    dense?: boolean;
    secondary?: React.ReactNode;
    // a trailing element (e.g. a settings icon button) rendered next to the title, outside the title's own hover/link
    action?: React.ReactNode;
    // wraps the content in its own bordered card - used for standalone entries not already inside a parent's card/button chrome
    card?: boolean;
  }>
> = ({
  icon,
  title,
  href,
  target,
  rel,
  compact = false,
  tooltip,
  dense = false,
  secondary,
  action,
  card = false,
  children
}) => {
  const safeTitle = title ?? href ?? '';

  if (dense) {
    return (
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        onClick={() => href && window.open(href, target)}
        sx={theme => ({
          cursor: 'pointer',
          width: '100%',
          p: 0.5,
          borderRadius: 1,
          transition: theme.transitions.create(['background-color']),
          '&:hover': { backgroundColor: 'action.hover' },
          '& a': { textDecoration: 'none', color: 'text.primary' }
        })}
      >
        {children || <RelatedIcon icon={icon} title={title} href={href} compact />}
        <ListItemText
          primary={
            <Typography
              component={Link}
              to={href ?? '#'}
              target={target}
              rel={rel}
              onClick={e => e.stopPropagation()}
              noWrap
              sx={{ '&:hover': { textDecoration: 'underline' } }}
            >
              {safeTitle}
            </Typography>
          }
          secondary={secondary}
          secondaryTypographyProps={{ component: 'div', noWrap: true }}
        />
        {action}
      </Stack>
    );
  }

  const tooltipContent = tooltip ?? <RelatedLinkTooltip title={safeTitle} href={href ?? ''} />;

  const content = (
    <Stack direction="row" p={compact ? 0.5 : 1} spacing={1} alignItems="center" sx={{ height: '100%' }}>
      {children || <RelatedIcon icon={icon} title={title} href={href} compact={compact} />}
      <Typography component={Link} to={href ?? '#'} target={target} rel={rel} onClick={e => e.stopPropagation()}>
        {safeTitle}
      </Typography>
    </Stack>
  );

  if (!card) {
    return (
      <Tooltip title={tooltipContent}>
        <Box
          onClick={() => href && window.open(href, target)}
          sx={{
            display: 'flex',
            cursor: 'pointer',
            '& a': { textDecoration: 'none', color: 'text.primary' }
          }}
        >
          {content}
        </Box>
      </Tooltip>
    );
  }

  return (
    <Tooltip title={tooltipContent}>
      <div style={{ display: 'flex' }}>
        <HowlerCard
          variant={compact ? 'outlined' : 'elevation'}
          key={href}
          onClick={() => href && window.open(href, target)}
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
          {content}
        </HowlerCard>
      </div>
    </Tooltip>
  );
};

export default RelatedLink;

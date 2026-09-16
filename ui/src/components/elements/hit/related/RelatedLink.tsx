import { ListItemText, Stack, Tooltip, Typography } from '@mui/material';
import HowlerCard from 'components/elements/display/HowlerCard';
import RelatedLinkTooltip from 'components/elements/hit/RelatedLinkTooltip';
import React, { type PropsWithChildren } from 'react';
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
    menuItem?: boolean;
    onNavigate?: () => void;
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
  menuItem,
  onNavigate,
  children
}) => {
  const safeTitle = title ?? href ?? '';

  if (dense) {
    return (
      <Stack direction="row" spacing={1} alignItems="center" sx={{ width: '100%' }}>
        <Stack
          component="a"
          href={href}
          target={target}
          rel={rel}
          role={menuItem ? 'menuitem' : undefined}
          onClick={onNavigate}
          direction="row"
          spacing={1}
          alignItems="center"
          sx={theme => ({
            color: 'text.primary',
            flex: 1,
            minWidth: 0,
            p: 0.5,
            borderRadius: 1,
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            transition: theme.transitions.create(['background-color']),
            '&:hover': { backgroundColor: 'action.hover', '& .pivot-title': { textDecoration: 'underline' } }
          })}
        >
          {children || <RelatedIcon icon={icon} title={title} href={href} compact />}
          <ListItemText
            primary={
              <Typography noWrap className="pivot-title">
                {safeTitle}
              </Typography>
            }
            secondary={secondary}
            secondaryTypographyProps={{ component: 'div', noWrap: true }}
          />
        </Stack>
        {action}
      </Stack>
    );
  }

  const tooltipContent = tooltip ?? <RelatedLinkTooltip title={safeTitle} href={href ?? ''} />;

  return (
    <Tooltip title={tooltipContent}>
      <div style={{ display: 'flex' }}>
        <HowlerCard
          variant={compact ? 'outlined' : 'elevation'}
          sx={[
            theme => ({
              backgroundColor: 'transparent',
              transition: theme.transitions.create(['border-color']),
              display: 'flex',
              alignItems: 'center',
              '&:hover': { borderColor: 'primary.main', '& a': { textDecoration: 'underline' } },
              '& > div': {
                height: '100%'
              },
              '& a': { textDecoration: 'none', color: 'text.primary' }
            }),
            !compact && { border: 'thin solid', borderColor: 'transparent' }
          ]}
        >
          <Stack
            component="a"
            href={href}
            target={target}
            rel={rel}
            onClick={onNavigate}
            direction="row"
            p={compact ? 0.5 : 1}
            spacing={1}
            alignItems="center"
            sx={{
              color: 'text.primary',
              textDecoration: 'none'
            }}
          >
            {children || <RelatedIcon icon={icon} title={title} href={href} compact={compact} />}
            <Typography>{safeTitle}</Typography>
          </Stack>
        </HowlerCard>
      </div>
    </Tooltip>
  );
};

export default RelatedLink;

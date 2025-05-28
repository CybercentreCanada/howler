import { ChevronRight, ExpandLess, ExpandMore } from '@mui/icons-material';
import { Collapse, List, ListItemButton, ListItemIcon, ListItemText, Popover, Tooltip, useTheme } from '@mui/material';
import type { AppLeftNavGroup } from 'commons/components/app/AppConfigs';
import { useAppConfigs, useAppLeftNav, useAppUser } from 'commons/components/app/hooks';
import LeftNavItem from 'commons/components/leftnav/LeftNavItem';
import { memo, useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface LeftNavGroupProps {
  group: AppLeftNavGroup;
  onItemClick: () => void;
}

const GroupListItem = memo(
  ({
    group,
    leftNavOpen,
    collapseOpen,
    popoverOpen,
    onClick
  }: {
    group: AppLeftNavGroup;
    leftNavOpen: boolean;
    collapseOpen: boolean;
    popoverOpen;
    onClick: (event: React.MouseEvent) => void;
  }) => {
    const { t } = useTranslation();
    const title = group.i18nKey ? t(group.i18nKey) : group.title;
    const theme = useTheme();

    return (
      <Tooltip title={!leftNavOpen ? title : ''} aria-label={title} placement="right">
        <ListItemButton key={group.id} onClick={onClick} selected={popoverOpen}>
          {!leftNavOpen && (
            <ChevronRight
              sx={{
                position: 'absolute',
                right: 0,
                width: 16,
                height: 16,
                transform: popoverOpen && 'rotate(180deg)',
                transition: theme.transitions.create('transform', {
                  easing: theme.transitions.easing.sharp,
                  duration: popoverOpen
                    ? theme.transitions.duration.leavingScreen
                    : theme.transitions.duration.enteringScreen
                })
              }}
              fontSize="inherit"
            />
          )}

          <ListItemIcon>{group.icon}</ListItemIcon>
          <ListItemText primary={title} />
          {collapseOpen ? <ExpandLess color="action" /> : <ExpandMore color="action" />}
        </ListItemButton>
      </Tooltip>
    );
  }
);

const LeftNavGroup = ({ group, onItemClick }: LeftNavGroupProps) => {
  const user = useAppUser();
  const leftnav = useAppLeftNav();
  const { preferences } = useAppConfigs();
  const [popoverTarget, setPopoverTarget] = useState<(EventTarget & Element) | undefined>();
  const [collapseOpen, setCollapseOpen] = useState(false);

  const groupHasIcons = group.items.some(i => !!i.icon);

  const handleClick = useCallback(
    (event: React.MouseEvent) => {
      if (leftnav.open) {
        setCollapseOpen(!collapseOpen);
      } else {
        setPopoverTarget(event ? event.currentTarget : undefined);
      }
    },
    [leftnav.open, collapseOpen]
  );

  const onClosePopover = useCallback(() => setPopoverTarget(undefined), []);

  useEffect(() => {
    if (!leftnav.open && collapseOpen) {
      setCollapseOpen(false);
    }
  }, [leftnav.open, collapseOpen]);

  return user.validateProps(group.userPropValidators) ? (
    <div>
      <GroupListItem
        group={group}
        leftNavOpen={leftnav.open}
        collapseOpen={collapseOpen}
        onClick={handleClick}
        popoverOpen={!!popoverTarget}
      />
      <Collapse in={collapseOpen} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          {group.items.map(i => (
            <LeftNavItem
              key={i.id}
              context="group"
              item={i}
              hideIcon={preferences.leftnav.hideNestedIcons}
              onClick={onItemClick}
            />
          ))}
        </List>
      </Collapse>
      <Popover
        open={!!popoverTarget}
        onClose={onClosePopover}
        onClick={onClosePopover}
        anchorEl={popoverTarget}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right'
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left'
        }}
      >
        <List disablePadding>
          {group.items.map(i => (
            <LeftNavItem
              popover
              context="group"
              key={i.id}
              item={i}
              hideIcon={preferences.leftnav.hideNestedIcons || !groupHasIcons}
              onClick={onItemClick}
            />
          ))}
        </List>
      </Popover>
    </div>
  ) : null;
};

export default memo(LeftNavGroup);

import {
  AppBar,
  Button,
  IconButton,
  Toolbar,
  Tooltip,
  useTheme,
  type ButtonProps,
  type IconButtonProps
} from '@mui/material';
import { useAppBar, useAppBarHeight, useAppLayout } from 'commons/components/app/hooks';
import { memo } from 'react';

export type PageHeaderAction = {
  key?: string;
  title?: string;
  tooltip?: string;
  icon?: React.ReactNode;
  color?: 'primary' | 'secondary';
  action?: () => void;
  btnProp?: ButtonProps | IconButtonProps;
};

type PageHeaderProps = {
  children?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  actions?: PageHeaderAction[];
  isSticky?: boolean;
  top?: number;
  elevation?: number;
  backgroundColor?: string;
  className?: string;
};

const PageHeader: React.FC<PageHeaderProps> = ({
  children,
  left,
  right,
  actions,
  backgroundColor,
  className,
  isSticky = false,
  top = null,
  elevation = 0
}) => {
  const theme = useTheme();
  const layout = useAppLayout();
  const appbar = useAppBar();
  const appBarHeight = useAppBarHeight();
  const barWillHide = layout.current !== 'top' && appbar.autoHide;

  return (
    <AppBar
      id="header1"
      position={isSticky ? 'sticky' : 'relative'}
      style={{
        top: top !== null ? top : isSticky ? (barWillHide ? 0 : appBarHeight) : null,
        backgroundColor: backgroundColor || theme.palette.background.default,
        zIndex: !isSticky ? theme.zIndex.appBar - 100 : null
      }}
      className={className}
      elevation={elevation}
      color="inherit"
    >
      {children}
      {(left || right || actions) && (
        <Toolbar style={{ minHeight: 0 }} disableGutters>
          <div style={{ flexGrow: 1 }}>{left}</div>
          <div>
            {actions &&
              actions.map((a, i) => {
                let act = null;
                if (a.title) {
                  act = (
                    <Button
                      key={a.tooltip ? null : a.key ? a.key : `ph-action-${i}`}
                      startIcon={a.icon}
                      color={a.color}
                      onClick={a.action}
                      {...(a.btnProp as ButtonProps)}
                      style={{ marginRight: theme.spacing(1) }}
                    >
                      {a.title}
                    </Button>
                  );
                } else {
                  act = (
                    <IconButton
                      key={a.tooltip ? null : a.key ? a.key : `ph-action-${i}`}
                      color={a.color}
                      onClick={a.action}
                      {...(a.btnProp as IconButtonProps)}
                      style={{ marginRight: theme.spacing(1) }}
                      size="large"
                    >
                      {a.icon}
                    </IconButton>
                  );
                }
                return a.tooltip ? (
                  <Tooltip key={a.key ? a.key : `ph-action-${i}`} title={a.tooltip}>
                    {act}
                  </Tooltip>
                ) : (
                  act
                );
              })}
          </div>
          <div>{right}</div>
        </Toolbar>
      )}
    </AppBar>
  );
};

export default memo(PageHeader);

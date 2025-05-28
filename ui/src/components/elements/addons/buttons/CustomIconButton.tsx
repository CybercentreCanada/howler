import {
  alpha,
  CircularProgress,
  darken,
  emphasize,
  IconButton,
  type IconButtonProps,
  lighten,
  Link as MuiLink,
  Tooltip,
  useTheme
} from '@mui/material';
import { type HTMLAttributeAnchorTarget, type ReactNode, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { isMuiButtonColor, type MuiButtonColorType } from '.';

export type CustomIconButtonProps = Omit<IconButtonProps, 'color'> & {
  progress?: boolean | number;
  transparent?: boolean;
  solid?: boolean;
  color?: string;
  route?: string;
  href?: string;
  tooltip?: string | ReactNode;
  target?: HTMLAttributeAnchorTarget;
  clickableWithProgress?: boolean;
};

const CustomIconButton = ({
  progress,
  transparent,
  solid,
  color,
  route,
  href,
  target,
  tooltip,
  disabled,
  children,
  clickableWithProgress = false,
  ...props
}: CustomIconButtonProps) => {
  const theme = useTheme();

  const requestedColor = color || 'primary';

  const isMuiColor = isMuiButtonColor(requestedColor);

  const sx = useMemo(() => {
    if (isMuiColor) {
      return props.sx || {};
    }
    const _bgColor = !transparent && solid ? requestedColor : alpha(requestedColor, 0.2);
    const _color = !transparent && solid ? theme.palette.getContrastText(requestedColor) : requestedColor;
    return {
      ...(props.sx && { ...props.sx }),
      color: _color,
      backgroundColor: transparent ? 'transparent' : _bgColor,
      '&:hover': {
        backgroundColor: transparent ? _bgColor : darken(_bgColor, 0.2)
      },
      '&:disabled': {
        backgroundColor: !transparent ? lighten(_bgColor, 0.1) : null
      }
    };
  }, [requestedColor, solid, transparent, props.sx, isMuiColor, theme]);

  const progressColor = useMemo(() => {
    const _color = isMuiColor ? theme.palette[requestedColor].main : requestedColor;
    return solid ? emphasize(_color, 0.5) : _color;
  }, [solid, requestedColor, isMuiColor, theme]);

  let _IconButton = (
    <IconButton
      {...props}
      disabled={(!clickableWithProgress && !!progress) || disabled}
      color={isMuiColor ? (color as MuiButtonColorType) : 'inherit'}
      sx={sx}
    >
      {progress ? (
        <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          {children}
          {
            <CircularProgress
              disableShrink
              size={props.size === 'large' ? 52 : props.size === 'small' ? 28 : 40}
              style={{
                position: 'absolute',
                color: progressColor,
                animationDuration: typeof progress === 'number' ? `${progress}s` : null
              }}
            />
          }
        </div>
      ) : (
        children
      )}
    </IconButton>
  );

  if (tooltip) {
    _IconButton = (
      <Tooltip title={tooltip}>
        <span>{_IconButton}</span>
      </Tooltip>
    );
  }

  if (route) {
    _IconButton = <Link to={route}>{_IconButton}</Link>;
  } else if (href) {
    _IconButton = (
      <MuiLink href={href} target={target ?? '_new'}>
        {_IconButton}
      </MuiLink>
    );
  }

  return _IconButton;
};

export default CustomIconButton;

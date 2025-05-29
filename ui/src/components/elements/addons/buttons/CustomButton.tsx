import type { ButtonProps } from '@mui/material';
import { alpha, Button, CircularProgress, darken, emphasize, Link as MuiLink, Tooltip, useTheme } from '@mui/material';
import type { ReactNode } from 'react';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { MuiButtonColorType } from '.';
import { isMuiButtonColor } from '.';

export type TuiButtonProps = Omit<ButtonProps, 'color'> & {
  solid?: boolean;
  color?: string;
  route?: string;
  href?: string;
  progress?: boolean;
  tooltip?: string | ReactNode;
};

const CustomButton = ({ solid, color, route, href, progress, tooltip, variant, ...props }: TuiButtonProps) => {
  const theme = useTheme();

  const requestedColor = color || 'primary';

  const isMuiColor = isMuiButtonColor(requestedColor);

  const _solid = useMemo(() => solid || variant === 'contained', [solid, variant]);

  const sx = useMemo(() => {
    if (isMuiColor) {
      return props.sx || {};
    }
    const transparent = variant === 'outlined' || variant === 'text' || !variant;
    const _bgColor = !transparent && _solid ? requestedColor : alpha(requestedColor, 0.2);
    const _color = !transparent && _solid ? theme.palette.getContrastText(requestedColor) : requestedColor;
    return {
      ...(props.sx && { ...props.sx }),
      color: _color,
      backgroundColor: transparent ? 'transparent' : _bgColor,
      '&:hover': {
        backgroundColor: transparent ? _bgColor : darken(_bgColor, 0.2)
      }
    };
  }, [_solid, requestedColor, variant, props.sx, isMuiColor, theme]);

  const progressColor = useMemo(() => {
    const _color = isMuiColor ? theme.palette[requestedColor].main : requestedColor;
    return _solid ? emphasize(_color, 0.5) : _color;
  }, [_solid, requestedColor, isMuiColor, theme]);

  let ColorButton = (
    <Button
      {...props}
      variant={variant}
      color={isMuiColor ? (color as MuiButtonColorType) : 'inherit'}
      sx={sx}
      startIcon={
        progress ? (
          <CircularProgress
            size={props.size === 'large' ? 22 : props.size === 'small' ? 18 : 20}
            sx={{ color: progressColor }}
          />
        ) : (
          props.startIcon
        )
      }
    />
  );

  if (tooltip) {
    ColorButton = (
      <Tooltip title={tooltip}>
        <span>{ColorButton}</span>
      </Tooltip>
    );
  }

  if (route) {
    ColorButton = (
      <Link to={route} style={{ textDecoration: 'none' }}>
        {ColorButton}
      </Link>
    );
  } else if (href) {
    ColorButton = (
      <MuiLink href={href} style={{ textDecoration: 'none' }} target="_new">
        {ColorButton}
      </MuiLink>
    );
  }

  return ColorButton;
};

export default CustomButton;

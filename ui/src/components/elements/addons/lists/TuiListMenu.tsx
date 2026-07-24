import { styled } from '@mui/material';
import type { CSSProperties, ReactElement } from 'react';
import { memo } from 'react';

const MY_PROPS = ['permanent', 'placement'];

type PlacementBox = {
  top: number | undefined;
  right: number | undefined;
  bottom: number | undefined;
  left: number | undefined;
};

const PLACEMENTS = {
  right: { top: 0, right: 0, bottom: 0, left: undefined } as PlacementBox,
  left: { top: 0, right: undefined, bottom: 0, left: 0 } as PlacementBox,
  'top-left': { top: 0, right: undefined, bottom: undefined, left: 0 } as PlacementBox,
  'top-right': { top: 0, right: 0, bottom: undefined, left: undefined } as PlacementBox,
  'bottom-left': { top: undefined, right: undefined, bottom: 0, left: 0 } as PlacementBox,
  'bottom-right': { top: undefined, right: 0, bottom: 0, left: undefined } as PlacementBox
};

type TuiListMenuProps = {
  permanent?: boolean;
  placement?: TuiListMenuPlacement;
  style?: CSSProperties;
  className?: string;
  children: ReactElement | ReactElement[];
};

export type TuiListMenuPlacement = keyof typeof PLACEMENTS;

const TuiListMenuRoot = styled('div', { shouldForwardProp: prop => !MY_PROPS.includes(prop as string) })<{
  permanent: boolean;
  placement: TuiListMenuPlacement;
}>(({ theme, permanent, placement }) => {
  const position = PLACEMENTS[placement];
  return {
    ...position,
    zIndex: position ? 100 : undefined,
    display: permanent ? 'flex' : 'none',
    position: position ? 'absolute' : 'inherit',
    alignItems: 'center',
    margin: 'auto',
    backgroundColor: theme.palette.background.default,
    '& button': {
      marginRight: theme.spacing(1),
      boxShadow: theme.shadows[4]
    }
  };
});

// TODO: placement property (top-left, top-right, bottom-left, bottom-right)
const TuiListMenu = ({ style, className, permanent, placement, children }: TuiListMenuProps) => {
  return (
    <TuiListMenuRoot
      permanent={!!permanent}
      placement={placement ?? 'right'}
      style={style}
      className={`actions ${className || ''}`}
      onClick={event => event.stopPropagation()}
    >
      {children}
    </TuiListMenuRoot>
  );
};

export default memo(TuiListMenu);

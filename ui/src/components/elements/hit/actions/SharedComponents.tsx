import { Badge, styled } from '@mui/material';
import { blueGrey } from '@mui/material/colors';
import type { ReactNode } from 'react';

export type ActionButton = {
  name: string;
  actionFunction?: () => void;
  key?: string;
  icon?: ReactNode;
};

export type Keybinds = {
  [key: string]: () => void;
};

export const TOP_ROW = ['legitimate', 'false-positive', 'ambiguous', 'development', 'security'];

export const ASSESSMENT_KEYBINDS = ['A', 'S', 'D', 'F', 'G', 'Z', 'X', 'C', 'V', 'B'];

export const VOTE_OPTIONS: ActionButton[] = [
  { name: 'Benign', key: 'Q' },
  { name: 'Obscure', key: 'W' },
  { name: 'Malicious', key: 'E' }
];

export const StyledBadge = styled(Badge)({
  '& .MuiBadge-badge': {
    borderRadius: '4px',
    background: blueGrey[400],
    fontSize: 9,
    height: '15px',
    minWidth: '15px',
    padding: '0',
    right: '5px',
    top: '2.5px'
  }
});

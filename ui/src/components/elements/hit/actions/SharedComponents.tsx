import type { StyledComponent } from '@emotion/styled';
import { Badge, styled, type BadgeProps } from '@mui/material';
import { blueGrey } from '@mui/material/colors';
import type { ReactNode } from 'react';

export type ActionButton = {
  type: 'assessment' | 'action' | 'vote';
  name: string;
  actionFunction: () => void;
  key?: string;
  i18nKey?: string;
  icon?: ReactNode;
};

export type Keybinds = {
  [key: string]: () => void;
};

export const TOP_ROW = ['legitimate', 'false-positive', 'ambiguous', 'development', 'security'];

export const ASSESSMENT_KEYBINDS = ['A', 'S', 'D', 'F', 'G', 'Z', 'X', 'C', 'V', 'B'];

export const VOTE_OPTIONS: Partial<ActionButton>[] = [
  { name: 'Benign', key: 'Q', type: 'vote' },
  { name: 'Obscure', key: 'W', type: 'vote' },
  { name: 'Malicious', key: 'E', type: 'vote' }
];

export const StyledBadge: StyledComponent<BadgeProps> = styled(Badge)({
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

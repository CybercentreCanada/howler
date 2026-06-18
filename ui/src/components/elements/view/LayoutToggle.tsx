import { List, TableChart } from '@mui/icons-material';
import { ToggleButton, ToggleButtonGroup } from '@mui/material';

export type HowlerViewLayoutType = 'list' | 'grid';

const LayoutToggle = ({
  displayType,
  setDisplayType,
  size
}: {
  displayType: HowlerViewLayoutType;
  setDisplayType: (type: HowlerViewLayoutType) => void;
  size?: 'small' | 'medium' | 'large';
}) => {
  return (
    <ToggleButtonGroup
      exclusive
      value={displayType}
      onChange={(__, value) => setDisplayType(value)}
      size={size ?? 'small'}
    >
      <ToggleButton value="list">
        <List fontSize={size ?? 'medium'} />
      </ToggleButton>
      <ToggleButton value="grid">
        <TableChart fontSize={size ?? 'medium'} />
      </ToggleButton>
    </ToggleButtonGroup>
  );
};

export default LayoutToggle;

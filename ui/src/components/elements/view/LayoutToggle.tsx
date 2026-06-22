import { List, TableChart } from '@mui/icons-material';
import { ToggleButton, ToggleButtonGroup } from '@mui/material';

export type HowlerViewLayoutType = 'list' | 'grid' | null;

const LayoutToggle = ({
  displayType,
  setDisplayType,
  size,
  allowNullValue = false
}: {
  displayType: HowlerViewLayoutType;
  setDisplayType: (type: HowlerViewLayoutType) => void;
  size?: 'small' | 'medium' | 'large';
  allowNullValue?: boolean;
}) => {
  return (
    <ToggleButtonGroup
      exclusive
      value={displayType}
      onChange={(__, value) => {
        if (!value && !allowNullValue) return;
        setDisplayType(value);
      }}
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

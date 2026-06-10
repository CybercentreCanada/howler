import { List, TableChart } from '@mui/icons-material';
import { ToggleButton, ToggleButtonGroup } from '@mui/material';

export type HowlerViewLayoutType = 'list' | 'grid';

const LayoutToggle = ({
  displayType,
  setDisplayType
}: {
  displayType: HowlerViewLayoutType;
  setDisplayType: (type: HowlerViewLayoutType) => void;
}) => {
  return (
    <ToggleButtonGroup exclusive value={displayType} onChange={(__, value) => setDisplayType(value)} size="small">
      <ToggleButton value="list">
        <List />
      </ToggleButton>
      <ToggleButton value="grid">
        <TableChart />
      </ToggleButton>
    </ToggleButtonGroup>
  );
};

export default LayoutToggle;

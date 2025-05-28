import { memo } from 'react';

const FlexOne = ({ children = null }) => {
  return <div style={{ flex: 1 }}>{children}</div>;
};
export default memo(FlexOne);

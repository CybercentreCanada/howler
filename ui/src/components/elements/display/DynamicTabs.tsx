import { Box, Tab, Tabs } from '@mui/material';
import * as React from 'react';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const CustomTabPanel: React.FC<TabPanelProps> = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div role="tabpanel" hidden={value !== index} id={`tabpanel-${index}`} aria-labelledby={`tab-${index}`} {...other}>
      {value === index && <Box sx={{ p: 1 }}>{children}</Box>}
    </div>
  );
};

const a11yProps = (index: number) => {
  return {
    id: `tab-${index}`,
    'aria-controls': `tabpanel-${index}`
  };
};

const DynamicTabs: React.FC<{ tabs: { title: string; children: React.ReactNode }[] }> = ({ tabs }) => {
  const [value, setValue] = React.useState(0);

  const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={value} onChange={handleChange} aria-label="dynamic tabs">
          {tabs.map((t, index) => (
            <Tab key={t.title} label={t.title} {...a11yProps(index)} />
          ))}
        </Tabs>
      </Box>
      {tabs.map((t, index) => (
        <CustomTabPanel key={t.title} value={value} index={index}>
          {t.children}
        </CustomTabPanel>
      ))}
    </Box>
  );
};

export default DynamicTabs;

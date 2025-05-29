import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';
import type { FC, ReactNode } from 'react';

const SettingsSection: FC<{ title: string; colSpan: number; children: ReactNode }> = ({ title, colSpan, children }) => {
  return (
    <TableContainer
      sx={{
        '& table tr:last-child td': {
          borderBottom: 0
        }
      }}
      component={Paper}
    >
      <Table aria-label={title}>
        <TableHead>
          <TableRow>
            <TableCell colSpan={colSpan}>
              <Typography variant="h6">{title}</Typography>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>{children}</TableBody>
      </Table>
    </TableContainer>
  );
};

export default SettingsSection;

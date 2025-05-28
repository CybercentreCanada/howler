import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Accordion, AccordionDetails, AccordionSummary, Box, Typography } from '@mui/material';
import React, { type PropsWithChildren } from 'react';
import ErrorOccured from './ErrorOccured';

class ErrorBoundary extends React.Component<PropsWithChildren<{}>, { hasError: boolean; error: Error }> {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error: error };
  }

  componentDidCatch(error: Error): void {
    this.setState({ hasError: true, error: error });
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box pt={6} textAlign="center" fontSize={20}>
          <ErrorOccured />
          <Accordion elevation={0}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls="panel1-content" id="panel1-header">
              <Typography align="center" sx={{ width: '100%', fontSize: '1.2rem' }} variant="h5">
                {this.state.error.message}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <code>
                <Typography variant="h6">{this.state.error.stack}</Typography>
              </code>
            </AccordionDetails>
          </Accordion>
        </Box>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;

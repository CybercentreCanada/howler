import { ExpandMore } from '@mui/icons-material';
import { Accordion, AccordionDetails, AccordionSummary, Box, Typography } from '@mui/material';
import React, { type PropsWithChildren } from 'react';
import { useLocation } from 'react-router-dom';
import ErrorOccured from './ErrorOccured';

type ErrorBoundaryProps = PropsWithChildren<{
  locationKey?: string;
}>;

class ErrorBoundaryComponent extends React.Component<ErrorBoundaryProps, { hasError: boolean; error: Error | null }> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error };
  }

  componentDidCatch(error: Error): void {
    this.setState({ hasError: true, error: error });
  }

  componentDidUpdate(previousProps: ErrorBoundaryProps): void {
    if (this.props.locationKey !== previousProps.locationKey && this.state.hasError) {
      this.setState({ hasError: false, error: null });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box pt={6} textAlign="center" fontSize={20}>
          <ErrorOccured />
          <Accordion elevation={0}>
            <AccordionSummary expandIcon={<ExpandMore />} aria-controls="panel1-content" id="panel1-header">
              <Typography align="center" sx={{ width: '100%', fontSize: '1.2rem' }} variant="h5">
                {this.state.error?.message}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <code>
                <Typography variant="h6">{this.state.error?.stack}</Typography>
              </code>
            </AccordionDetails>
          </Accordion>
        </Box>
      );
    }
    return this.props.children;
  }
}

const ErrorBoundary = ({ children }: PropsWithChildren) => {
  const location = useLocation();

  return <ErrorBoundaryComponent locationKey={location.key}>{children}</ErrorBoundaryComponent>;
};

export default ErrorBoundary;

import { styled } from '@mui/material';
import { SnackbarProvider } from 'notistack';

const StyledSnackbarProvider = styled(SnackbarProvider)`
  & .SnackbarItem-message {
    word-break: break-all;
  }
`;

// Wrap SnackbarProvider into its own component so we can use theme base breakpoints
//  to calculate css styles.
// This has to be done as child of AppContextProvider and in a separate component in order
//  to ensure the ThemeProvider is already initialized.
export default function AppSnackbarProvider({ children }) {
  return <StyledSnackbarProvider>{children}</StyledSnackbarProvider>;
}

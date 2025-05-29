import { Apps } from '@mui/icons-material';
import { Divider, List, Skeleton, Toolbar, styled, useMediaQuery, useTheme } from '@mui/material';
import { AppUserAvatar } from 'commons/components//topnav/UserProfile';
import type { AppLeftNavElement } from 'commons/components/app/AppConfigs';
import {
  useAppBreadcrumbs,
  useAppConfigs,
  useAppLayout,
  useAppLeftNav,
  useAppQuickSearch
} from 'commons/components/app/hooks';
import { AppBarBase } from 'commons/components/topnav/AppBar';

/**
 * Utility component to render the  skeleton of the left navigation menu elements.
 *
 * The specified properties are simply passed down to each child [ButtonSkeleton] component.
 *
 * @param props
 */
interface LeftNavElementsSkeletonProps {
  // eslint-disable-next-line react/require-default-props
  withText?: boolean;
  elements: AppLeftNavElement[];
}

interface ButtonSkeletonProps {
  style: { [styleAttr: string]: any };
  // eslint-disable-next-line react/require-default-props
  withText?: boolean;
  [propName: string]: any;
}

const StyledContainer = styled('div')(({ theme }) => ({
  position: 'fixed',
  zIndex: theme.zIndex.appBar + 1000,
  top: 0,
  left: 0,
  right: 0,
  bottom: 0
}));

const StyledTopLayout = styled('div')({
  height: '100%',
  display: 'flex',
  flexDirection: 'column'
});

const StyledLeftLayout = styled('div')({
  height: '100%',
  display: 'flex',
  flexDirection: 'row'
});

const StyledContent = styled('div')(({ theme }) => ({
  display: 'flex',
  flexDirection: 'row',
  flex: 1,
  backgroundColor: theme.palette.background.default
}));

const StyledContentLeft = styled('div')(({ theme }) => ({
  border: '1px solid',
  borderColor: theme.palette.divider,
  borderTopColor: 'transparent',
  backgroundColor: theme.palette.background.paper,
  marginRight: 5,
  flex: '0 0 auto',
  [theme.breakpoints.down('sm')]: {
    display: 'none'
  }
}));

const StyledContentRight = styled('div')({
  flex: '1 1 auto'
});

const StyledQuickSearchSkeleton = styled(Skeleton)(({ theme }) => ({
  padding: theme.spacing(2),
  [theme.breakpoints.down('sm')]: {
    display: 'none'
  }
}));

const StyledBreadcrumbsSkeleton = styled(Skeleton)(({ theme }) => ({
  height: theme.spacing(4),
  [theme.breakpoints.down('sm')]: {
    display: 'none'
  }
}));

const ButtonSkeleton = ({ style, withText, ...boxProps }: ButtonSkeletonProps) => {
  const theme = useTheme();
  const isXs = useMediaQuery(theme.breakpoints.only('xs'));

  return (
    <div style={{ ...style, height: 48, display: 'flex', flexDirection: 'row' }} {...boxProps}>
      <Skeleton variant="text" animation="wave">
        <Apps />
      </Skeleton>
      {withText && (
        <Skeleton
          variant="text"
          animation="wave"
          style={{ flexGrow: 1, marginLeft: isXs ? theme.spacing(2) : theme.spacing(4) }}
        />
      )}
    </div>
  );
};

const LeftNavElementsSkeleton = ({ elements, withText }: LeftNavElementsSkeletonProps) => {
  const theme = useTheme();
  return (
    <>
      {elements.map((element, i) => {
        if (element.type === 'divider') {
          return <Divider key={`leftnav-sklt-divider-${i}`} />;
        }
        return (
          <ButtonSkeleton
            withText={withText}
            style={{
              paddingTop: theme.spacing(1),
              paddingBottom: theme.spacing(1),
              paddingLeft: theme.spacing(2),
              paddingRight: theme.spacing(2)
            }}
            key={`leftnav-sklt-${element.element.id}`}
          />
        );
      })}
    </>
  );
};

/**
 * A Skeleton for the side layout...
 */
const SideLayoutSkeleton = () => {
  // TUI hooks
  const configs = useAppConfigs();
  const leftnav = useAppLeftNav();
  const breadcrumbs = useAppBreadcrumbs();
  const quicksearch = useAppQuickSearch();
  const { left, leftAfterBreadcrumbs } = configs.preferences.topnav;

  // React hooks.
  const muiTheme = useTheme();
  const isXs = useMediaQuery(muiTheme.breakpoints.only('xs'));
  const isSm = useMediaQuery(muiTheme.breakpoints.only('sm'));
  const isMdUp = useMediaQuery(muiTheme.breakpoints.up('md'));

  // basic styling.
  const sp1 = muiTheme.spacing(1);
  const sp2 = muiTheme.spacing(2);
  const sp7 = muiTheme.spacing(7);
  const showTopBarBreadcrumbs = breadcrumbs.show && !isSm;
  const showSpacer = isXs || !quicksearch.show || (isMdUp && (breadcrumbs.show || left || leftAfterBreadcrumbs));

  return (
    <StyledContainer>
      <StyledLeftLayout>
        <StyledContent>
          <StyledContentLeft style={{ width: leftnav.open ? configs.preferences.leftnav.width : sp7 }}>
            <Toolbar disableGutters>
              <ButtonSkeleton
                withText={leftnav.open}
                style={{ paddingTop: sp1, paddingBottom: sp1, paddingLeft: sp2, paddingRight: sp2, flexGrow: 1 }}
              />
            </Toolbar>
            <Divider />
            <List disablePadding>
              <LeftNavElementsSkeleton elements={leftnav.elements} withText={leftnav.open} />
              {leftnav.elements?.length > 0 && <Divider />}
              <ButtonSkeleton
                withText={leftnav.open}
                style={{ paddingTop: sp1, paddingBottom: sp1, paddingLeft: sp2, paddingRight: sp2 }}
              />
            </List>
          </StyledContentLeft>
          <StyledContentRight>
            <AppBarBase>
              <Toolbar disableGutters style={{ paddingRight: sp2, paddingLeft: !isXs ? sp2 : null }}>
                {isXs && (
                  <ButtonSkeleton
                    withText={leftnav.open}
                    style={{
                      paddingTop: sp1,
                      paddingBottom: sp1,
                      paddingLeft: sp2,
                      paddingRight: sp2,
                      flexGrow: 1
                    }}
                  />
                )}
                {showTopBarBreadcrumbs && <StyledBreadcrumbsSkeleton variant="text" animation="wave" width={100} />}
                {showSpacer && <div style={{ flexGrow: 1 }} />}
                {quicksearch.show && (
                  <StyledQuickSearchSkeleton
                    variant="text"
                    animation="wave"
                    width={showTopBarBreadcrumbs ? 358 : 'auto'}
                    style={{ flexGrow: !showTopBarBreadcrumbs ? 1 : 0 }}
                  />
                )}
                <ButtonSkeleton
                  withText={false}
                  style={{
                    paddingTop: sp1,
                    paddingBottom: sp1,
                    paddingLeft: sp2,
                    paddingRight: sp2,
                    marginLeft: sp1,
                    marginRight: sp1
                  }}
                />
                <Skeleton animation="wave" variant="circular">
                  <AppUserAvatar />
                </Skeleton>
              </Toolbar>
            </AppBarBase>
          </StyledContentRight>
        </StyledContent>
      </StyledLeftLayout>
    </StyledContainer>
  );
};

/**
 * A Skeleton for the top layout.
 */
const TopLayoutSkeleton = () => {
  // TUI hooks
  const configs = useAppConfigs();
  const leftnav = useAppLeftNav();
  const breadcrumbs = useAppBreadcrumbs();
  const quicksearch = useAppQuickSearch();
  const { left, leftAfterBreadcrumbs } = configs.preferences.topnav;

  // React hooks
  const muiTheme = useTheme();
  const isXs = useMediaQuery(muiTheme.breakpoints.only('xs'));
  const isSm = useMediaQuery(muiTheme.breakpoints.only('sm'));
  const isMdUp = useMediaQuery(muiTheme.breakpoints.up('md'));

  //
  const showSpacer = isXs || !quicksearch.show || (isMdUp && (breadcrumbs.show || left || leftAfterBreadcrumbs));
  const showTopBarBreadcrumbs = breadcrumbs.show && !isSm;
  const sp1 = muiTheme.spacing(1);
  const sp2 = muiTheme.spacing(2);
  const sp3 = muiTheme.spacing(3);
  const sp4 = muiTheme.spacing(4);
  const sp7 = muiTheme.spacing(7);

  return (
    <StyledContainer>
      <StyledTopLayout>
        <AppBarBase>
          <Toolbar style={{ paddingRight: sp2 }} disableGutters>
            <ButtonSkeleton
              withText={false}
              style={{ paddingTop: sp1, paddingBottom: sp1, paddingLeft: sp2, paddingRight: sp4 }}
            />
            <Skeleton variant="text" animation="wave" style={{ marginRight: sp3 }}>
              <div style={{ fontSize: '1.5rem', letterSpacing: '-1px' }}>{configs.preferences.appName}</div>
            </Skeleton>
            {showTopBarBreadcrumbs && <StyledBreadcrumbsSkeleton variant="text" animation="wave" width={100} />}
            {showSpacer && <div style={{ flexGrow: 1 }} />}
            {quicksearch.show && (
              <StyledQuickSearchSkeleton
                variant="text"
                animation="wave"
                width={showTopBarBreadcrumbs ? 300 : 'auto'}
                style={{ flexGrow: !showTopBarBreadcrumbs ? 1 : 0 }}
              />
            )}
            <ButtonSkeleton
              withText={false}
              style={{
                paddingTop: sp1,
                paddingBottom: sp1,
                paddingLeft: sp2,
                paddingRight: sp2,
                marginLeft: sp1,
                marginRight: sp1
              }}
            />
            <Skeleton animation="wave" variant="circular">
              <AppUserAvatar />
            </Skeleton>
          </Toolbar>
        </AppBarBase>
        <StyledContent>
          <StyledContentLeft style={{ width: leftnav.open ? configs.preferences.leftnav.width : sp7 }}>
            <List disablePadding>
              <LeftNavElementsSkeleton elements={leftnav.elements} withText={leftnav.open} />
              {leftnav.elements?.length > 0 && <Divider />}
              <ButtonSkeleton
                withText={leftnav.open}
                style={{ paddingTop: sp1, paddingBottom: sp1, paddingLeft: sp2, paddingRight: sp2 }}
              />
            </List>
          </StyledContentLeft>
          <StyledContentRight />
        </StyledContent>
      </StyledTopLayout>
    </StyledContainer>
  );
};

/**
 * Default Skeleton component that will render either [TopLayoutSkeleton] or [SideLayoutSkeleton] based on [useAppLayout::currentLayout].
 */
const LayoutSkeleton = () => {
  const layout = useAppLayout();
  return layout.current === 'top' ? <TopLayoutSkeleton /> : <SideLayoutSkeleton />;
};

// Default exported component
export default LayoutSkeleton;

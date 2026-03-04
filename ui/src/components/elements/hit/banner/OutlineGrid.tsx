import { Box } from '@mui/material';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import type { HitLayout } from '../HitLayout';
import BannerWrapper from './BannerWrapper';

const OutlineGrid: FC<{ hit: Hit; layout: HitLayout }> = ({ hit, layout }) => {
  let gridTemplateRows: string[] = [];
  const entries = [];

  if (hit.howler?.outline?.threat) {
    gridTemplateRows.push('threat-title threat-content');
    entries.push(
      <BannerWrapper
        gridSection="threat"
        i18nKey="hit.header.threat"
        value={hit.howler.outline.threat}
        field="howler.outline.threat"
        layout={layout}
        hit={hit}
      />
    );
  }

  if (hit.howler?.outline?.target) {
    gridTemplateRows.push('target-title target-content');
    entries.push(
      <BannerWrapper
        gridSection="target"
        i18nKey="hit.header.target"
        value={hit.howler.outline.target}
        field="howler.outline.target"
        layout={layout}
        hit={hit}
      />
    );
  }

  if (hit.howler?.outline?.indicators?.length > 0) {
    gridTemplateRows.push('indicators-title indicators-content');
    entries.push(
      <BannerWrapper
        gridSection="indicators"
        i18nKey="hit.header.indicators"
        value={hit.howler.outline.indicators}
        field="howler.outline.indicators"
        layout={layout}
        hit={hit}
      />
    );
  }

  if (hit.howler?.outline?.summary) {
    gridTemplateRows.push('summary-title summary-content');
    entries.push(
      <BannerWrapper
        gridSection="summary"
        i18nKey="hit.header.summary"
        value={hit.howler.outline.summary}
        paragraph
        textOverflow="wrap"
        field="howler.outline.summary"
        layout={layout}
        hit={hit}
      />
    );
  }

  return (
    <Box
      sx={theme => ({
        display: 'grid',
        gridTemplateColumns: 'auto 1fr',
        columnGap: theme.spacing(1),
        columnCount: 2,
        columnRule: '5px solid red',
        gridTemplateAreas: gridTemplateRows.map(line => `"${line.trim()}"`).join('\n')
      })}
    >
      {entries}
    </Box>
  );
};

export default OutlineGrid;

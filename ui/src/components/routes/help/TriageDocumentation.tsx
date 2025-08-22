import { ExpandMore } from '@mui/icons-material';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Card,
  Chip,
  emphasize,
  Stack,
  styled,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { useAppBar, useAppLayout, useAppUser } from 'commons/components/app/hooks';
import type { AppTocItem } from 'commons/components/display/AppToc';
import PageCenter from 'commons/components/pages/PageCenter';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useScrollRestoration } from 'components/hooks/useScrollRestoration';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { memo, useContext, useMemo, type FC, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import HelpTabs from './components/HelpTabs';

const TableRoot = styled('div')(({ theme }) => ({
  '& .MuiTable-root': {
    paddingRight: 8,
    paddingLeft: 8
  },
  '& .MuiTableHead-root': {
    backgroundColor: theme.palette.mode === 'dark' ? '#404040' : '#EEE',
    whiteSpace: 'nowrap'
  }
}));

const PageCenterRoot = styled(PageCenter)(({ theme }) => ({
  '& .MuiPaper-root': {
    backgroundColor: emphasize(theme.palette.background.default, 0.05)
  },
  '.multipleEx': {
    marginBlockStart: theme.spacing(1),
    paddingInlineStart: theme.spacing(2)
  },
  '.padded': {
    paddingBottom: theme.spacing(1),
    paddingTop: theme.spacing(1)
  },
  '.pre': {
    fontFamily: 'monospace',
    fontSize: '1rem',
    margin: theme.spacing(0, 0, 1, 0),
    padding: theme.spacing(1, 1.5),
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word'
  },
  '.paragraph': {
    marginTop: '-96px',
    '& .spacer': {
      height: theme.spacing(14)
    },
    '& h6': {
      fontWeight: 300
    }
  },
  '.autoHide': {
    marginTop: theme.spacing(0),
    paddingTop: theme.spacing(4)
  }
}));

const TOC_CONFIGS: AppTocItem[] = [
  { id: 'Intro' },
  { id: 'Assessment' },
  {
    id: 'Escalation',
    subItems: [{ id: 'fields.legend' }, { id: 'fields.idx_hit' }, { id: 'fields.idx_user', is_admin: true }]
  },
  { id: 'Rationale' },
  { id: 'wildcard' },
  {
    id: 'regex',
    subItems: [
      { id: 'regex.anchoring' },
      { id: 'regex.chars' },
      { id: 'regex.any' },
      { id: 'regex.oneplus' },
      { id: 'regex.zeroplus' },
      { id: 'regex.zeroone' },
      { id: 'regex.minmax' },
      { id: 'regex.grouping' },
      { id: 'regex.alternation' },
      { id: 'regex.class' }
    ]
  },
  { id: 'fuzziness' },
  { id: 'proximity' },
  { id: 'ranges', subItems: [{ id: 'ranges.datemath' }] },
  { id: 'operator' },
  { id: 'grouping' },
  { id: 'reserved' }
];

const Paragraph: FC<{ id: string; children: ReactElement | ReactElement[] }> = memo(({ id, children }) => {
  const { autoHide: autoHideAppbar } = useAppBar();
  const { current: currentLayout } = useAppLayout();
  return (
    <div id={id} className={`paragraph ${autoHideAppbar && currentLayout !== 'top' ? 'autoHide' : ''}`}>
      <div className="spacer" />
      {children}
    </div>
  );
});

const SquareChip = styled(Chip)(({ theme }) => ({
  borderRadius: 3,
  height: 20,
  margin: theme.spacing(0.1),
  fontSize: 'smaller'
}));

const TriageDocumentation: FC = () => {
  const { t } = useTranslation(['helpSearch']);

  const { user } = useAppUser<HowlerUser>();
  const { config } = useContext(ApiConfigContext);
  const location = useLocation();
  const theme = useTheme();
  const useHorizontal = useMediaQuery(theme.breakpoints.down(1700));
  useScrollRestoration();

  const indexes = useMemo(() => {
    return config?.indexes || [];
  }, [config]);

  return (
    <PageCenterRoot margin={4} width="100%" maxWidth="1750px" textAlign="left">
      <Stack sx={{ flexDirection: useHorizontal ? 'column' : 'row', '& h1': { mt: 0 } }}>
        <HelpTabs value={location.hash || '#overview'}>
          {TOC_CONFIGS.flatMap(value => [
            <Tab
              key={value.id}
              href={`#${value.id}`}
              label={<Typography variant="caption">{t(value.id)}</Typography>}
              value={`#${value.id}`}
            />,
            ...(!useHorizontal && value.subItems ? value.subItems : []).map(
              subItem =>
                (!subItem.is_admin || user.is_admin) && (
                  <Tab
                    key={subItem.id}
                    sx={{ '& > span': { pl: 1 } }}
                    href={`#${subItem.id}`}
                    label={<Typography variant="caption">{t(subItem.id)}</Typography>}
                    value={`#${subItem.id}`}
                  />
                )
            )
          ])}
        </HelpTabs>
        <Box>
          <Typography variant="h4">Howler Data Fields</Typography>
          <Typography variant="subtitle2">
            Howler fields in the Howler Data model pertaining to triaging alerts
          </Typography>

          <Paragraph id="Assessment">
            <Typography variant="h5">Assessment</Typography>
            <>
              The assessment field of an alert is used by analysts to make an assessment on the alert for if it is a
              valid hit
            </>
          </Paragraph>

          <Paragraph id="escalation">
            <Typography variant="h5">Escalation</Typography>
            <>The escalation field of an alert is used by analysts to decide the priority of the alert</>
          </Paragraph>

          <Paragraph id="rationale">
            <Typography variant="h5">Rationale</Typography>
            <>
              The rationale field of an alert is used by analysts to give their rationale on their assessment for a
              specific alert
            </>
          </Paragraph>

          <Paragraph id="fields">
            <Typography variant="h5">{t('fields')}</Typography>
            <>{t('fields.text')}</>
            <Typography variant="subtitle2" className="padded">
              {t('exemples')}
            </Typography>
            <ul className="multipleEx">
              <li>
                {t('fields.ex1.title')}
                <Card variant="outlined" className="pre">
                  {t('fields.ex1')}
                </Card>
              </li>
              <li>
                {t('fields.ex2.title')}
                <Card variant="outlined" className="pre">
                  {t('fields.ex2')}
                </Card>
              </li>
              <li>
                {t('fields.ex3.title')}
                <Card variant="outlined" className="pre">
                  {t('fields.ex3')}
                </Card>
              </li>
              <li>
                {t('fields.ex4.title')}
                <Card variant="outlined" className="pre">
                  {t('fields.ex4')}
                </Card>
              </li>
              <li>
                {t('fields.ex5.title')}
                <Card variant="outlined" className="pre">
                  {t('fields.ex5')}
                </Card>
              </li>
            </ul>
            <div className="padded">{t('fields.text2')}</div>
            <div>
              <b>
                <i>{`${t('fields.important')}:`}</i>
              </b>
              {` ${t('fields.important.text')}`}
            </div>
          </Paragraph>

          <Paragraph id="text vs keywords">
            <Typography variant="h5">{t('fields.textvskeywords')}</Typography>
            <>{t('fields.textvskeywords.description')}</>
            <Typography variant="subtitle2" className="padded">
              {t('fields.textvskeywords.keywordfamily')}
            </Typography>
            <ul className="multipleEx">
              <li>
                <Card variant="outlined" className="pre">
                  {t('fields.textvskeywords.wildcard')}
                </Card>
                {t('fields.textvskeywords.wildcard.description')}
              </li>
              <li>
                <Card variant="outlined" className="pre">
                  {t('fields.textvskeywords.keyword')}
                </Card>
                {t('fields.textvskeywords.keyword.description')}
              </li>
              <li>
                <Card variant="outlined" className="pre">
                  {t('fields.textvskeywords.constantkeyword')}
                </Card>
                {t('fields.textvskeywords.constantkeyword.description')}
              </li>
            </ul>

            <Typography variant="subtitle2" className="padded">
              {t('fields.textvskeywords.keyword.more.info')}{' '}
              <a
                href="https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/keyword"
                style={{ color: 'info', textDecoration: 'underline' }}
                // eslint-disable-next-line react/jsx-no-literals
              >
                https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/keyword
              </a>
            </Typography>

            <Typography variant="subtitle2" className="padded">
              {t('fields.textvskeywords.textfamily')}
            </Typography>
            <ul className="multipleEx">
              <li>
                <Card variant="outlined" className="pre">
                  {t('fields.textvskeywords.text')}
                </Card>
                {t('fields.textvskeywords.text.description')}
              </li>
              <li>
                <Card variant="outlined" className="pre">
                  {t('fields.textvskeywords.matchonlytext')}
                </Card>
                {t('fields.textvskeywords.matchonlytext.description')}
              </li>
            </ul>

            <Typography variant="subtitle2" className="padded">
              {t('fields.textvskeywords.text.more.info')}{' '}
              <a
                href="https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/text"
                style={{ color: 'info', textDecoration: 'underline' }}
                // eslint-disable-next-line react/jsx-no-literals
              >
                https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/text
              </a>
            </Typography>

            <Typography variant="subtitle2" className="padded">
              {t('fields.textvskeywords.text.keyword.compare')}{' '}
              <a
                href="https://www.elastic.co/blog/strings-are-dead-long-live-strings"
                style={{ color: 'info', textDecoration: 'underline' }}
                // eslint-disable-next-line react/jsx-no-literals
              >
                https://www.elastic.co/blog/strings-are-dead-long-live-strings
              </a>
            </Typography>

            <div></div>
          </Paragraph>

          <Paragraph id="fields.legend">
            <Typography variant="h6">{t('fields.legend')}</Typography>
            <>{t('fields.legend.text')}</>
            <ul>
              <li>
                <b>{'text'}</b>
                {`: ${t('fields.legend.text_field')}`}
              </li>
              <li>
                <b>{'ip'}</b>
                {`: ${t('fields.legend.ip_field')}`}
              </li>
              <li>
                <SquareChip color="primary" size="small" label={t('fields.att.default')} />:{' '}
                {t('fields.legend.default')}
              </li>
              <li>
                <SquareChip color="warning" size="small" label={t('fields.att.list')} />: {t('fields.legend.list')}
              </li>
              <li>
                <SquareChip color="info" size="small" label={t('fields.att.stored')} />: {t('fields.legend.stored')}
              </li>
            </ul>
          </Paragraph>

          {Object.keys(indexes).map(idx => (
            <Accordion key={idx} sx={{ mb: 2, backgroundColor: 'background.paper' }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">{t(`fields.idx_${idx}`)}</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ px: '0 !important', mt: -6 }}>
                <Paragraph id={`fields.idx_${idx}`}>
                  <TableRoot>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>{t('fields.table.name')}</TableCell>
                          <TableCell>{t('fields.table.type')}</TableCell>
                          <TableCell>{t('fields.table.attrib')}</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.keys(indexes[idx]).map(
                          field =>
                            indexes[idx][field].indexed && (
                              <TableRow hover key={field}>
                                <TableCell width="50%" style={{ wordBreak: 'break-word' }}>
                                  {field}
                                </TableCell>
                                <TableCell>{indexes[idx][field].type}</TableCell>
                                <TableCell>
                                  {indexes[idx][field].stored && (
                                    <SquareChip
                                      color="info"
                                      size="small"
                                      label={t('fields.att.stored')}
                                      // tooltip={t('fields.att.stored.tooltip')}
                                    />
                                  )}
                                  {indexes[idx][field].list && (
                                    <SquareChip
                                      color="warning"
                                      size="small"
                                      label={t('fields.att.list')}
                                      // tooltip={t('fields.att.list.tooltip')}
                                    />
                                  )}
                                  {indexes[idx][field].default && (
                                    <SquareChip
                                      color="primary"
                                      size="small"
                                      label={t('fields.att.default')}
                                      // tooltip={t('fields.att.default.tooltip')}
                                    />
                                  )}
                                </TableCell>
                              </TableRow>
                            )
                        )}
                      </TableBody>
                    </Table>
                  </TableRoot>
                </Paragraph>
              </AccordionDetails>
            </Accordion>
          ))}

          <Paragraph id="wildcard">
            <Typography variant="h5">{t('wildcard')}</Typography>
            <div className="padded">{t('wildcard.text')}</div>
            <Card variant="outlined" className="pre">
              {t('wildcard.ex')}
            </Card>
            <div className="padded">{t('wildcard.text2')}</div>
            <div>
              <b>
                <i>{`${t('wildcard.note')}:`}</i>
              </b>
              {` ${t('wildcard.note.text')}`}
            </div>
          </Paragraph>

          <Paragraph id="regex">
            <Typography variant="h5">{t('regex')}</Typography>
            <div className="padded">{t('regex.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.ex')}
            </Card>
            <div>
              <b>
                <i>{t('regex.warning')}</i>
              </b>
            </div>
            <div className="padded">{t('regex.warning.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.warning.ex')}
            </Card>
            <div className="padded">{t('regex.warning.follow')}</div>
          </Paragraph>

          <Paragraph id="regex.anchoring">
            <Typography variant="h6">{t('regex.anchoring')}</Typography>
            <div className="padded">{t('regex.anchoring.text')}</div>
            <div className="padded">{t('regex.anchoring.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.anchoring.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.chars">
            <Typography variant="h6">{t('regex.chars')}</Typography>
            <div className="padded">{t('regex.chars.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.chars.ex')}
            </Card>
            <div className="padded">{t('regex.chars.text2')}</div>
            <div className="padded">{t('regex.chars.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.chars.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.any">
            <Typography variant="h6">{t('regex.any')}</Typography>
            <div className="padded">{t('regex.any.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.any.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.oneplus">
            <Typography variant="h6">{t('regex.oneplus')}</Typography>
            <div className="padded">{t('regex.oneplus.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.oneplus.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.zeroplus">
            <Typography variant="h6">{t('regex.zeroplus')}</Typography>
            <div className="padded">{t('regex.zeroplus.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.zeroplus.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.zeroone">
            <Typography variant="h6">{t('regex.zeroone')}</Typography>
            <div className="padded">{t('regex.zeroone.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.zeroone.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.minmax">
            <Typography variant="h6">{t('regex.minmax')}</Typography>
            <div className="padded">{t('regex.minmax.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.minmax.ex')}
            </Card>
            <div className="padded">{t('regex.minmax.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.minmax.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.grouping">
            <Typography variant="h6">{t('regex.grouping')}</Typography>
            <div className="padded">{t('regex.grouping.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.grouping.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.alternation">
            <Typography variant="h6">{t('regex.alternation')}</Typography>
            <div className="padded">{t('regex.alternation.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.alternation.ex')}
            </Card>
          </Paragraph>

          <Paragraph id="regex.class">
            <Typography variant="h6">{t('regex.class')}</Typography>
            <div className="padded">{t('regex.class.text')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.class.ex')}
            </Card>
            <div className="padded">{t('regex.class.text2')}</div>
            <div className="padded">{t('regex.class.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('regex.class.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="fuzziness">
            <Typography variant="h5">{t('fuzziness')}</Typography>
            <div className="padded">{t('fuzziness.text')}</div>
            <Card variant="outlined" className="pre">
              {t('fuzziness.ex')}
            </Card>
            <div className="padded">{t('fuzziness.text2')}</div>
            <div className="padded">{t('fuzziness.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('fuzziness.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="proximity">
            <Typography variant="h5">{t('proximity')}</Typography>
            <div className="padded">{t('proximity.text')}</div>
            <Card variant="outlined" className="pre">
              {t('proximity.ex')}
            </Card>
            <div className="padded">{t('proximity.text2')}</div>
          </Paragraph>

          <Paragraph id="ranges">
            <Typography variant="h5">{t('ranges')}</Typography>
            <>{t('ranges.text')}</>
            <Typography variant="subtitle2" className="padded">
              {t('exemples')}
            </Typography>
            <ul className="multipleEx">
              <li>
                {t('ranges.ex1.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex1')}
                </Card>
              </li>
              <li>
                {t('ranges.ex2.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex2')}
                </Card>
              </li>
              <li>
                {t('ranges.ex3.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex3')}
                </Card>
              </li>
              <li>
                {t('ranges.ex4.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex4')}
                </Card>
              </li>
              <li>
                {t('ranges.ex5.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex5')}
                </Card>
              </li>
              <li>
                {t('ranges.ex6.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex6')}
                </Card>
              </li>
              <li>
                {t('ranges.ex7.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex7')}
                </Card>
              </li>
            </ul>
            <div className="padded">{t('ranges.text2')}</div>
            <ul className="multipleEx">
              <li>
                {t('ranges.ex8.title')}
                <Card variant="outlined" className="pre">
                  {t('ranges.ex8')}
                </Card>
              </li>
            </ul>
            <div className="padded">{t('ranges.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('ranges.ex9')}
            </Card>
            <div className="padded">{t('ranges.text4')}</div>
            <Card variant="outlined" className="pre">
              {t('ranges.ex10')}
            </Card>
          </Paragraph>

          <Paragraph id="ranges.datemath">
            <Typography variant="h6">{t('ranges.datemath')}</Typography>
            <div className="padded">{t('ranges.datemath.text')}</div>
            <ul>
              <li>{t('ranges.datemath.list1')}</li>
              <li>{t('ranges.datemath.list2')}</li>
              <li>{t('ranges.datemath.list3')}</li>
            </ul>
            <div className="padded">{t('ranges.datemath.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('ranges.datemath.ex1')}
            </Card>
            <div className="padded">{t('ranges.datemath.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('ranges.datemath.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="operator">
            <Typography variant="h5">{t('operator')}</Typography>
            <div className="padded">{t('operator.text')}</div>
            <div className="padded">{t('operator.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('operator.ex1')}
            </Card>
            <div className="padded">{t('operator.text3')}</div>
            <ul>
              <li>{t('operator.list1')}</li>
              <li>{t('operator.list2')}</li>
              <li>{t('operator.list3')}</li>
            </ul>
            <div className="padded">{t('operator.text4')}</div>
            <Card variant="outlined" className="pre">
              {t('operator.ex2')}
            </Card>
            <div className="padded">{t('operator.text5')}</div>
          </Paragraph>

          <Paragraph id="grouping">
            <Typography variant="h5">{t('grouping')}</Typography>
            <div className="padded">{t('grouping.text')}</div>
            <Card variant="outlined" className="pre">
              {t('grouping.ex')}
            </Card>
            <div className="padded">{t('grouping.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('grouping.ex2')}
            </Card>
          </Paragraph>

          <Paragraph id="reserved">
            <Typography variant="h5">{t('reserved')}</Typography>
            <div className="padded">{t('reserved.text')}</div>
            <div className="padded">{t('reserved.text2')}</div>
            <Card variant="outlined" className="pre">
              {t('reserved.ex')}
            </Card>
            <div className="padded">{t('reserved.text3')}</div>
            <Card variant="outlined" className="pre">
              {t('reserved.ex2')}
            </Card>
            <div className="padded">{t('reserved.text4')}</div>
            <div className="padded">
              <b>
                <i>{t('reserved.note')}</i>
              </b>
              {`: ${t('reserved.text5')}`}
            </div>
          </Paragraph>
        </Box>
      </Stack>
    </PageCenterRoot>
  );
};

export default TriageDocumentation;

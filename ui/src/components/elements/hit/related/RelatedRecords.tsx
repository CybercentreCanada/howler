import { Link } from '@mui/icons-material';
import api from 'api';
import ChipPopper from 'components/elements/display/ChipPopper';
import useMyApi from 'components/hooks/useMyApi';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const RelatedRecords: FC<{ hit: Hit }> = ({ hit }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const [open, setOpen] = useState(false);
  const [records, setRecords] = useState([]);

  const related = useMemo(() => hit?.howler.related ?? [], [hit?.howler.related]);

  useEffect(() => {
    if (!open) {
      return;
    }

    (async () => {
      const result = await dispatchApi(
        api.v2.search.post('hit,observable,case', {
          query: `howler.id:(${related.join(' OR ')}) OR case_id:(${related.join(' OR ')})`
        })
      );

      console.log(result);
    })();
  });

  return (
    <ChipPopper
      // eslint-disable-next-line jsx-a11y/anchor-is-valid
      icon={<Link />}
      label={t('hit.header.related', { count: hit.howler.related.length })}
      slotProps={{ chip: { disabled: related.length < 1 } }}
      onToggle={_open => setOpen(_open)}
    >
      <h1>hi</h1>
    </ChipPopper>
  );
};

export default memo(RelatedRecords);

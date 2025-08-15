import { Button, type ButtonProps } from '@mui/material';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import useMyActionFunctions from 'components/routes/action/useMyActionFunctions';
import type { Action } from 'models/entities/generated/Action';
import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const ActionButton: FC<{ actionId: string; hitId: string; label: string } & ButtonProps> = ({
  actionId,
  hitId,
  label,
  ...otherProps
}) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();

  const { executeAction } = useMyActionFunctions();

  const [action, setAction] = useState<Action>(null);

  useEffect(() => {
    dispatchApi(api.search.action.post({ query: `action_id:${actionId}`, rows: 1 })).then(result =>
      setAction(result.items[0])
    );
  }, [actionId, dispatchApi]);

  return (
    <Button
      variant={otherProps.variant ?? 'outlined'}
      disabled={!action}
      onClick={() => executeAction(actionId, `howler.id:${hitId}`)}
      color={otherProps.color ?? 'primary'}
    >
      {label ?? action?.name ?? t('loading')}
    </Button>
  );
};

export default ActionButton;

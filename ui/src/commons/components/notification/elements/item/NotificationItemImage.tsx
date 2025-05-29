import { memo, type FC } from 'react';

export const NotificationItemImage: FC<{ image?: string }> = memo(
  ({ image = null }) =>
    image && (
      <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
        <img
          src={image}
          alt={image}
          style={{
            maxWidth: '256px',
            maxHeight: '256px',
            borderRadius: '5px',
            marginTop: '8px'
          }}
        />
      </div>
    )
);

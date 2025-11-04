import { render, screen, waitFor } from '@testing-library/react';
import { omit } from 'lodash-es';
import { MemoryRouter } from 'react-router-dom';
import MockLocalStorage from 'tests/MockLocalStorage';
import { MY_LOCAL_STORAGE_PREFIX, StorageKey } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import AnalyticHitComments from './AnalyticHitComments';

// Mock the API
const mockApiSearchHitPost = vi.fn();
vi.mock('api', () => ({
  default: {
    search: {
      hit: {
        post: (...args) => mockApiSearchHitPost(...args)
      }
    }
  }
}));

// Mock local storage
const mockLocalStorage: Storage = new MockLocalStorage() as any;
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

// Mock hooks
vi.mock('components/hooks/useMyLocalStorage', () => ({
  useMyLocalStorageItem: (key: StorageKey, defaultValue: any) => {
    const storageKey = `${MY_LOCAL_STORAGE_PREFIX}.${key}`;
    const storedValue = mockLocalStorage.getItem(storageKey);
    const value = storedValue ? JSON.parse(storedValue) : defaultValue;
    return [value, vi.fn()];
  }
}));

vi.mock('components/hooks/useMyUserList', () => ({
  default: (userIds: Set<string>) => {
    const userMap = {};
    Array.from(userIds).forEach(id => {
      userMap[id] = { username: `user_${id}`, name: `User ${id}` };
    });
    return userMap;
  }
}));

// Mock Comment component
vi.mock('components/elements/Comment', () => ({
  default: ({ comment, onClick, extra }) => (
    <div id={`comment-${comment.id}`} onClick={onClick}>
      <span id={`comment-user-${comment.id}`}>
        {'Comment by '}
        {comment.user}
      </span>
      <span id={`comment-text-${comment.id}`}>{comment.text}</span>
      {extra}
    </div>
  )
}));

// Mock MUI components
vi.mock('@mui/material', () => ({
  Chip: ({ label, ...props }) => (
    <span role="detection-chip" {...omit(props, ['flexItem', 'sx'])}>
      {label}
    </span>
  ),
  Divider: ({ ...props }) => <hr id="divider" {...omit(props, ['flexItem', 'sx'])} />,
  LinearProgress: ({ ...props }) => <div role="progressbar" id="loading" {...omit(props, ['flexItem', 'sx'])} />,
  Stack: ({ children, ...props }) => (
    <div id="stack" {...omit(props, ['flexItem', 'sx'])}>
      {children}
    </div>
  )
}));

// Mock utils
vi.mock('utils/utils', () => ({
  compareTimestamp: (a: string, b: string) => new Date(b).getTime() - new Date(a).getTime()
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate
    // useSearchParams: () => [new URLSearchParams()]
  };
});

// Mock data
const mockAnalytic = {
  name: 'test-analytic',
  description: 'Test analytic description'
};

const mockHitResponse = {
  items: [
    {
      howler: {
        id: 'hit1',
        detection: 'Detection 1',
        comment: [
          {
            id: 'comment1',
            user: 'user1',
            text: 'First comment',
            timestamp: '2023-11-01T10:00:00Z'
          },
          {
            id: 'comment2',
            user: 'user2',
            text: 'Second comment',
            timestamp: '2023-11-01T11:00:00Z'
          }
        ]
      }
    },
    {
      howler: {
        id: 'hit2',
        detection: 'Detection 2',
        comment: [
          {
            id: 'comment3',
            user: 'user1',
            text: 'Third comment',
            timestamp: '2023-11-01T12:00:00Z'
          }
        ]
      }
    }
  ]
};

const Wrapper = ({ children, searchParams = '' }) => (
  <MemoryRouter initialEntries={[`/analytics/test?${searchParams}`]}>{children}</MemoryRouter>
);

describe('AnalyticHitComments', () => {
  beforeEach(() => {
    mockLocalStorage.clear();
    mockApiSearchHitPost.mockClear();
    mockApiSearchHitPost.mockResolvedValue(mockHitResponse);
    mockNavigate.mockClear();

    // Set default page count
    mockLocalStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.PAGE_COUNT}`, JSON.stringify(25));
  });

  describe('Lucene query usage', () => {
    it('should use the correct Lucene query with analytic name', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledWith({
          query: `howler.analytic:"${sanitizeLuceneQuery(mockAnalytic.name)}" AND _exists_:howler.comment`,
          rows: 25
        });
      });
    });

    it('should use the page count from local storage in the query', async () => {
      // Set a custom page count
      mockLocalStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.PAGE_COUNT}`, JSON.stringify(50));

      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledWith({
          query: `howler.analytic:"${sanitizeLuceneQuery(mockAnalytic.name)}" AND _exists_:howler.comment`,
          rows: 50
        });
      });
    });

    it('should not make API call when no analytic is provided', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={null} />
        </Wrapper>
      );

      // Wait a bit to ensure no call is made
      await new Promise(resolve => setTimeout(resolve, 100));

      expect(mockApiSearchHitPost).not.toHaveBeenCalled();
    });

    it('should show loading state while fetching data', async () => {
      // Make the API call take longer
      let resolvePromise;
      const delayedPromise = new Promise(resolve => {
        resolvePromise = resolve;
      });
      mockApiSearchHitPost.mockReturnValue(delayedPromise);

      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      // Should show loading indicator
      expect(screen.getByRole('progressbar')).toBeInTheDocument();

      // Resolve the promise
      resolvePromise(mockHitResponse);

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });
    });
  });

  describe('Comment rendering', () => {
    it('should render all comments from the API response', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
        expect(screen.getByTestId('comment-comment2')).toBeInTheDocument();
        expect(screen.getByTestId('comment-comment3')).toBeInTheDocument();
      });

      // Check comment content using more specific selectors
      expect(screen.getByTestId('comment-user-comment1')).toHaveTextContent('Comment by user1');
      expect(screen.getByTestId('comment-text-comment1')).toHaveTextContent('First comment');
      expect(screen.getByTestId('comment-user-comment2')).toHaveTextContent('Comment by user2');
      expect(screen.getByTestId('comment-text-comment2')).toHaveTextContent('Second comment');
      expect(screen.getByTestId('comment-text-comment3')).toHaveTextContent('Third comment');
    });

    it('should render comments sorted by timestamp in descending order', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
      });

      const comments = screen.getAllByTestId(/comment-comment/);
      // Based on timestamps, comment3 (12:00) should be first, then comment2 (11:00), then comment1 (10:00)
      expect(comments[0]).toHaveAttribute('id', 'comment-comment1');
      expect(comments[1]).toHaveAttribute('id', 'comment-comment2');
      expect(comments[2]).toHaveAttribute('id', 'comment-comment3');
    });

    it('should render detection chips when no filter is applied', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
      });

      // Look for detection chips
      const detectionChips = screen.getAllByRole('detection-chip');
      expect(detectionChips.length).toEqual(3);
    });

    it('should filter comments by detection when filter parameter is present', async () => {
      render(
        <Wrapper searchParams="filter=Detection 1">
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        // Should show comments from Detection 1 only
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
        expect(screen.getByTestId('comment-comment2')).toBeInTheDocument();
        expect(screen.queryByTestId('comment-comment3')).not.toBeInTheDocument();
      });
    });

    it('should not render detection chips when filter is applied', async () => {
      render(
        <Wrapper searchParams="filter=Detection 1">
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
      });

      // When filter is applied, no detection chips should be rendered
      expect(screen.queryAllByTestId('detection-chip')).toHaveLength(0);

      // Only comments from Detection 1 should be shown
      const comments = screen.getAllByTestId(/comment-comment/);
      expect(comments).toHaveLength(2); // Only comments from Detection 1
    });

    it('should handle empty response gracefully', async () => {
      mockApiSearchHitPost.mockResolvedValue({ items: [] });

      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalled();
      });

      // Should not render any comments
      expect(screen.queryByTestId(/comment-comment/)).not.toBeInTheDocument();
      // Should not show loading indicator
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });

    it('should navigate to hit page when comment is clicked', async () => {
      render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('comment-comment1')).toBeInTheDocument();
      });

      // Click on a comment
      screen.getByTestId('comment-comment1').click();

      expect(mockNavigate).toHaveBeenCalledWith('/hits/hit1');
    });
  });

  describe('Component lifecycle', () => {
    it('should refetch data when analytic changes', async () => {
      const { rerender } = render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledTimes(1);
      });

      // Change analytic
      const newAnalytic = { name: 'new-analytic', description: 'New analytic' };
      rerender(
        <Wrapper>
          <AnalyticHitComments analytic={newAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledTimes(2);
        expect(mockApiSearchHitPost).toHaveBeenLastCalledWith({
          query: `howler.analytic:${newAnalytic.name} AND _exists_:howler.comment`,
          rows: 25
        });
      });
    });

    it('should refetch data when page count changes', async () => {
      const { rerender } = render(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledTimes(1);
      });

      // Change page count in localStorage
      mockLocalStorage.setItem(`${MY_LOCAL_STORAGE_PREFIX}.${StorageKey.PAGE_COUNT}`, JSON.stringify(100));

      // Force rerender to trigger useEffect
      rerender(
        <Wrapper>
          <AnalyticHitComments analytic={mockAnalytic} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(mockApiSearchHitPost).toHaveBeenCalledTimes(2);
        expect(mockApiSearchHitPost).toHaveBeenLastCalledWith({
          query: `howler.analytic:${mockAnalytic.name} AND _exists_:howler.comment`,
          rows: 100
        });
      });
    });
  });
});

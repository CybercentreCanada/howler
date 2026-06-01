import { act, renderHook } from '@testing-library/react';
import type { HowlerSearchRequest } from 'api/search';
import { useContext } from 'react';
import SearchResponseProvider, {
  SearchResponseContext,
  type SearchResponseContextType,
  type SearchResponseState
} from './SearchResponseProvider';

const TEST_PAGE_SIZE = 25;
const TEST_TOTAL_COUNT = 100;

const makeWrapper = (initialResponse?: SearchResponseState<Item>) => {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <SearchResponseProvider<Item> idField="id" initialResponse={initialResponse}>
      {children}
    </SearchResponseProvider>
  );
  return Wrapper;
};

const renderProvider = (initialResponse?: SearchResponseState<Item>) => {
  return renderHook(() => useContext<SearchResponseContextType<Item>>(SearchResponseContext), {
    wrapper: makeWrapper(initialResponse)
  });
};

type Item = {
  id: string;
  name: string;
};

describe('push', () => {
  it("should add an item to the response if it doesn't exist", () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'existing' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.push({ id: '1', name: 'test' });
    });

    expect(hook.result.current.response).toEqual({
      items: [
        { id: '0', name: 'existing' },
        { id: '1', name: 'test' }
      ],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT + 1,
      removeCount: 0
    });
  });

  it('should replace an item in the response if it already exists', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'old' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.push({ id: '0', name: 'new' });
    });

    expect(hook.result.current.response).toEqual({
      items: [{ id: '0', name: 'new' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it('should update total but not add item if the response has the maximum number of items', () => {
    const items = Array.from({ length: TEST_PAGE_SIZE }, (_, i) => ({ id: i.toString(), name: `item${i}` }));
    const newItem = { id: TEST_PAGE_SIZE.toString(), name: 'test' };
    const hook = renderProvider({
      items,
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.push(newItem);
    });

    expect(hook.result.current.response?.items).not.toContainEqual(newItem);
    expect(hook.result.current.response).toEqual({
      items,
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT + 1,
      removeCount: 0
    });
  });

  it('should decrement removeCount if the item does not exist already', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'existing' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 1
    });

    act(() => {
      hook.result.current.push({ id: '1', name: 'test' });
    });

    expect(hook.result.current.response).not.toBeNull();
    expect(hook.result.current.response.removeCount).toBe(0);
  });

  it('should not decrement removeCount if the item already exists', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'existing' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 1
    });

    act(() => {
      hook.result.current.push({ id: '0', name: 'new' });
    });

    expect(hook.result.current.response).not.toBeNull();
    expect(hook.result.current.response.removeCount).toBe(1);
  });

  it('should keep response null if it is uninitiated', () => {
    const hook = renderProvider();

    act(() => {
      hook.result.current.push({ id: '0', name: 'test' });
    });

    expect(hook.result.current.response).toBeNull();
  });
});

describe('remove', () => {
  it('should remove an item from the response if it exists', () => {
    const hook = renderProvider({
      items: [
        { id: '0', name: 'item0' },
        { id: '1', name: 'item1' }
      ],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.remove('0');
    });

    expect(hook.result.current.response).toEqual({
      items: [{ id: '1', name: 'item1' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT - 1,
      removeCount: 1
    });
  });

  it('should ignore the remove if the item does not exist', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.remove('1');
    });

    expect(hook.result.current.response).toEqual({
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it('should keep response null if it is uninitiated', () => {
    const hook = renderProvider();

    act(() => {
      hook.result.current.remove('0');
    });

    expect(hook.result.current.response).toBeNull();
  });
});

describe('replace', () => {
  it('should replace an item in the response if it exists', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'old' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.replace('0', { id: undefined, name: 'new' });
    });

    expect(hook.result.current.response).toEqual({
      items: [{ id: '0', name: 'new' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it('should ignore the replace if the item does not exist', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    act(() => {
      hook.result.current.replace('1', { id: undefined, name: 'new' });
    });

    expect(hook.result.current.response).not.toContainEqual({ id: '1', name: 'new' });
    expect(hook.result.current.response).toEqual({
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it('should keep response null if it is uninitiated', () => {
    const hook = renderProvider();

    act(() => {
      hook.result.current.replace('0', { id: '0', name: 'new' });
    });

    expect(hook.result.current.response).toBeNull();
  });

  it('should throw error if item id does not match the id provided', () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'old' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    expect(() =>
      act(() => {
        hook.result.current.replace('0', { id: '1', name: 'new' });
      })
    ).toThrow(/id does not match/);
  });
});

describe('request', () => {
  const apiSearchMock = vi.fn();

  beforeEach(() => {
    apiSearchMock.mockReset();
  });

  it('should update the response with the result of the request', async () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: 0
    };

    apiSearchMock.mockResolvedValue({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT
    });

    await act(async () => {
      await hook.result.current.request(apiSearchMock, request);
    });

    expect(apiSearchMock).toHaveBeenCalledWith(request);
    expect(hook.result.current.response).toEqual({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it.for([
    { description: 'before', offset: 0 },
    { description: 'the same as', offset: TEST_PAGE_SIZE }
  ])('should reset removeCount if the offset is $description the current offset', async ({ offset }) => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'item' }],
      offset: TEST_PAGE_SIZE,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 5
    });

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: offset
    };

    apiSearchMock.mockResolvedValue({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT
    });

    await act(async () => {
      await hook.result.current.request(apiSearchMock, request);
    });

    expect(apiSearchMock).toHaveBeenCalledWith(request);
    expect(hook.result.current.response).toEqual({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 0
    });
  });

  it('should not reset removeCount if the offset is after the current offset', async () => {
    const hook = renderProvider({
      items: [{ id: '0', name: 'item' }],
      offset: TEST_PAGE_SIZE,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 5
    });

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: TEST_PAGE_SIZE * 2
    };

    apiSearchMock.mockResolvedValue({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT
    });

    await act(async () => {
      await hook.result.current.request(apiSearchMock, request);
    });

    expect(apiSearchMock).toHaveBeenCalledWith(request);
    expect(hook.result.current.response).toEqual({
      items: [{ id: '1', name: 'new' }],
      offset: request.offset,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 5
    });
  });

  it('should keep response undefined if the request fails', async () => {
    const hook = renderProvider();

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: 0
    };

    apiSearchMock.mockRejectedValue(new Error('Request failed'));

    await act(async () => {
      await hook.result.current.request(apiSearchMock, request).catch(() => {});
    });

    expect(apiSearchMock).toHaveBeenCalledWith(request);
    expect(hook.result.current.response).toBeNull();
  });

  it('should keep response unchanged if the request fails', async () => {
    const initialResponse = {
      items: [{ id: '0', name: 'item' }],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 5
    };
    const hook = renderProvider(initialResponse);

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: 0
    };

    apiSearchMock.mockRejectedValue(new Error('Request failed'));

    await act(async () => {
      await hook.result.current.request(apiSearchMock, request).catch(() => {});
    });

    expect(apiSearchMock).toHaveBeenCalledWith(request);
    expect(hook.result.current.response).toEqual(initialResponse);
  });

  it('should throw an error if the request throws an error', async () => {
    const hook = renderProvider();

    const request: HowlerSearchRequest = {
      query: 'test',
      rows: TEST_PAGE_SIZE,
      offset: 0
    };

    apiSearchMock.mockRejectedValue(new Error('Request failed'));

    await expect(
      act(async () => {
        await hook.result.current.request(apiSearchMock, request);
      })
    ).rejects.toThrow('Request failed');
  });
});

describe('getSearchRequestData', () => {
  it.for([
    { description: 'no remove count', removeCount: 0 },
    { description: 'with remove count', removeCount: 5 }
  ])('should modify offset if it is provided - $description', ({ removeCount }) => {
    const hook = renderProvider({
      items: [],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: removeCount
    });

    const modifiedRequest = hook.result.current.getSearchRequestData({ offset: TEST_PAGE_SIZE });

    expect(modifiedRequest.offset).toBe(TEST_PAGE_SIZE - removeCount);
  });

  it('should not modify offset if it is not provided', () => {
    const hook = renderProvider({
      items: [],
      offset: 0,
      rows: TEST_PAGE_SIZE,
      total: TEST_TOTAL_COUNT,
      removeCount: 5
    });

    const modifiedRequest = hook.result.current.getSearchRequestData({ query: 'value' });

    expect(modifiedRequest.offset).not.toBeDefined();
  });

  it('should not modify offset if response is uninitialised', () => {
    const hook = renderProvider();

    const modifiedRequest = hook.result.current.getSearchRequestData({ offset: TEST_PAGE_SIZE });

    expect(modifiedRequest.offset).toBe(TEST_PAGE_SIZE);
  });
});

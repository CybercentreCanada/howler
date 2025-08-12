export default class MockLocalStorage {
  constructor() {
    Object.defineProperty(this, 'getItem', {
      enumerable: false,
      value: vi.fn(key => (this[key] !== undefined ? this[key] : null))
    });
    Object.defineProperty(this, 'setItem', {
      enumerable: false,
      // not mentioned in the spec, but we must always coerce to a string
      value: vi.fn((key, val) => {
        this[key] = `${val}`;
      })
    });
    Object.defineProperty(this, 'removeItem', {
      enumerable: false,
      value: vi.fn(key => {
        delete this[key];
      })
    });
    Object.defineProperty(this, 'clear', {
      enumerable: false,
      value: vi.fn(() => {
        Object.keys(this).map(key => delete this[key]);
      })
    });
    Object.defineProperty(this, 'toString', {
      enumerable: false,
      value: vi.fn(() => {
        return '[object Storage]';
      })
    });
    Object.defineProperty(this, 'key', {
      enumerable: false,
      value: vi.fn(idx => Object.keys(this)[idx] || null)
    });
  } // end constructor

  get length() {
    return Object.keys(this).length;
  }

  // for backwards compatibility
  get __STORE__() {
    return this;
  }
}

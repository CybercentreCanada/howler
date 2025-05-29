export default class Throttler {
  private throttleId: NodeJS.Timeout = null;

  private delayId: NodeJS.Timeout = null;

  private msec: number = null;

  constructor(msec: number) {
    this.msec = msec;
    this.debounce = this.debounce.bind(this);
  }

  public throttle(fn: () => void): void {
    if (!this.throttleId) {
      fn();
      this.throttleId = setTimeout(() => {
        this.throttleId = null;
      }, this.msec);
    }
  }

  public debounce(fn: () => void): void {
    if (this.delayId) {
      clearTimeout(this.delayId);
    }
    this.delayId = setTimeout(fn, this.msec);
  }

  public delayAsync(fn: (...args: any[]) => Promise<any>, ...args: any[]): Promise<any> {
    if (this.delayId) {
      clearTimeout(this.delayId);
    }
    return new Promise((resolve, reject) => {
      this.delayId = setTimeout(async () => {
        try {
          resolve(await fn?.(...args));
        } catch (error) {
          reject(error);
        }
      }, this.msec);
    });
  }
}

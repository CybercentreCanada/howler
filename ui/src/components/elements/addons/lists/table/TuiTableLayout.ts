import type { TuiTableColumn } from '.';

export default class TuiTableLayout {
  private tableWidth: number;

  private bodyWidth: number;

  private columns: TuiTableColumn[] = [];

  private widths: { [column: string]: number };

  constructor(tableWidth: number, bodyWidth: number, columns: TuiTableColumn[]) {
    this.tableWidth = tableWidth;
    this.bodyWidth = bodyWidth;
    this.columns = columns;
    this.compute();
  }

  public getWidth(column?: string, header?: boolean) {
    if (column) {
      const extra = column && header && this.isLast(column) ? this.tableWidth - this.bodyWidth : 0;
      return extra > 0 ? this.widths[column] + extra : this.widths[column];
    }
    return this.bodyWidth;
  }

  private isLast(column: string): boolean {
    const index = this.columns.findIndex(c => c.column === column);
    return index === this.columns.length - 1;
  }

  private columnWidth(ratio: number) {
    return (ratio / 12) * this.bodyWidth;
  }

  private compute(): void {
    let _rw = this.bodyWidth;
    const _nw = this.columns.filter(c => !c.width);
    const _ww = this.columns.filter(c => !!c.width);

    this.widths = {};
    _ww.forEach(c => {
      const cw = this.columnWidth(c.width);
      this.widths[c.column] = cw;
      _rw -= cw;
    });

    const cw = _rw / _nw.length;
    _nw.forEach(c => {
      this.widths[c.column] = cw;
    });
  }
}

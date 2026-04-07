export function buildWindowedGridState({
  itemCount,
  columnCount,
  rowHeight,
  scrollTop,
  viewportHeight,
  overscanRows = 2,
}) {
  const safeColumns = Math.max(1, Number(columnCount) || 1);
  const safeRowHeight = Math.max(1, Number(rowHeight) || 1);
  const totalRows = Math.ceil((Number(itemCount) || 0) / safeColumns);
  const startRow = Math.max(
    0,
    Math.floor((Number(scrollTop) || 0) / safeRowHeight) - overscanRows,
  );
  const visibleRowCount =
    Math.ceil((Number(viewportHeight) || 0) / safeRowHeight) + overscanRows * 2;
  const endRow = Math.min(totalRows, startRow + visibleRowCount);

  return {
    startIndex: startRow * safeColumns,
    endIndex: Math.min(Number(itemCount) || 0, endRow * safeColumns),
    topPadding: startRow * safeRowHeight,
    bottomPadding: Math.max(0, (totalRows - endRow) * safeRowHeight),
  };
}

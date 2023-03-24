import {
  SlIcon,
  SlIconButton,
  SlOption,
  SlRadioButton,
  SlRadioGroup,
  SlSelect,
} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {useSortBy, useTable} from 'react-table';
import {VariableSizeList as List} from 'react-window';
import styles from './table.module.css';

const TABLE_HEIGHT_PX = 300;
enum Colors {
  ORANGE = 'rgb(250, 222, 201)',
  YELLOW = 'rgb(253, 236, 200)',
  GREEN = 'rgb(219, 237, 219)',
  BLUE = 'rgb(211, 229, 239)',
  PURPLE = 'rgb(232, 222, 238)',
  RED = 'rgb(255, 226, 221)',
  GRAY = 'rgba(227, 226, 224, 0.5)',
}

const LABEL_COLORS = [
  Colors.ORANGE,
  Colors.BLUE,
  Colors.RED,
  Colors.GREEN,
  Colors.YELLOW,
  Colors.PURPLE,
];

const NO_LABEL = 'No label';
const NO_LABEL_COLOR = Colors.GRAY;

type FILTER_VIEW = 'all' | 'labeled' | 'unlabeled';

export interface TableExample {
  text: string;

  // Original data.
  rowIdx: number;
  prediction: number;

  label?: number;

  // Extra sortable metadata.
  metadata: {[columnName: string]: string | number};
}

interface TableProps {
  title: string;

  examples: TableExample[];
  labelSet: {[label: number]: string};

  tableHeightPx?: number;

  exampleRemoved?: (rowIdx: number) => void;
  labelSelected?: (rowIdx: number, label: number) => void;
  addExample?: (text: string, label: number) => void;
  sortBy?: Array<{
    id: string;
    desc: boolean;
  }>;
  rowIdxFilter?: number[];
}

const COLUMN_ID_CELL_CLASS_MAP: {[columnId: string]: string} = {
  text: styles.textCell,
  prediction: styles.predictionCell,
  label: styles.labelCell,
  correct: styles.correctCell,
  clear_row: styles.clearRowCell,
};

export const Table = React.memo(function Table({
  title,
  examples,
  labelSet,
  tableHeightPx,
  exampleRemoved,
  labelSelected,
  sortBy,
  rowIdxFilter,
}: TableProps): JSX.Element {
  // TODO: Switch this when switching the tab.
  const isLabeled = true;
  const [filterView, setFilterView] = React.useState<FILTER_VIEW>('all');

  const rowIdxFilterSet = new Set(rowIdxFilter);
  const {data, extraColumns, correct, numLabeledExamples, numTotalExamples} = React.useMemo(() => {
    let correct = 0;
    let numLabeledExamples = 0;

    let numTotalExamples = 0;

    let data = examples.filter((example) => {
      if (rowIdxFilter == null) {
        return true;
      }
      return rowIdxFilterSet.has(example.rowIdx);
    });

    numTotalExamples = data.length;
    data.forEach((example) => {
      if (example.prediction === example.label) {
        correct++;
      }
      if (example.label != null) {
        numLabeledExamples++;
      }
    });

    if (filterView === 'labeled') {
      data = data.filter((example) => example.label != null);
    } else if (filterView === 'unlabeled') {
      data = data.filter((example) => example.label == null);
    }

    const extraColumns = new Set();
    data = data.map((example) => {
      Object.keys(example.metadata).forEach((key) => extraColumns.add(key));
      return {
        rowIdx: example.rowIdx,
        text: example.text,
        prediction: example.prediction,
        label: example.label,
        metadata: example.metadata,
      };
    });
    return {
      data,
      extraColumns: Array.from(extraColumns) as string[],
      correct,
      numTotalExamples,
      numLabeledExamples,
    };
  }, [examples, rowIdxFilter, filterView]);

  const numUnlabeledExamples = numTotalExamples - numLabeledExamples;

  sortBy = sortBy || [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const initialState: any = React.useMemo(() => {
    return {sortBy};
  }, [sortBy]);

  const {getTableProps, getTableBodyProps, headerGroups, rows, prepareRow} = useTable(
    {
      columns: React.useMemo(
        () => [
          {
            id: 'clear_row',
            accessor: 'rowIdx',
            Cell: ({
              cell: {
                value,
                row: {index},
              },
            }: {
              cell: {value: number; row: {index: number}};
            }) => {
              const rowIdx = value;
              return data[index].label != null ? (
                <div className="w-4 mr-2 text-lg cursor-pointer">
                  <SlIcon name="x" onClick={() => exampleRemoved!(rowIdx)}></SlIcon>
                </div>
              ) : (
                <></>
              );
            },
          },

          {
            Header: 'Text',
            accessor: 'text',
            Cell: ({cell: {value}}: {cell: {value: string}}) => {
              return (
                <div>
                  <div className="h-full">{value}</div>
                </div>
              );
            },
          },
          ...extraColumns.map((columnName) => {
            return {
              Header: columnName,
              id: columnName,
              accessor: ({metadata}: {metadata: {[columnName: string]: string | number}}) => {
                return metadata![columnName] || -1;
              },
              sortType: 'basic',
              Cell: ({cell: {value}}: {cell: {value: number | string}}) => {
                return (
                  <div className="w-full text-sm text-center">
                    {typeof value === 'number' ? Math.floor(100 * value) : value}
                  </div>
                );
              },
            };
          }),
          {
            Header: 'Prediction',
            accessor: 'prediction',
            Cell: ({cell: {value}}: {cell: {value: number; row: {index: number}}}) => {
              const predictionColor = LABEL_COLORS[value];
              const predictionLabel = labelSet[value];
              return (
                <>
                  <div className={`${styles.labelPill}`} style={{background: predictionColor}}>
                    {predictionLabel}
                  </div>
                </>
              );
            },
          },
          {
            Header: 'Label',
            accessor: 'label',
            Cell: ({
              cell: {
                row: {index},
              },
            }: {
              cell: {value: number; row: {index: number}};
            }) => {
              return (
                <div className="font-sm flex flex-row">
                  <SlIconButton
                    name="dash-square"
                    label="Label as out-of-filter"
                    onClick={() => labelSelected!(data[index].rowIdx, 0)}
                  />
                  <SlIconButton
                    name="plus-square"
                    label="Label as in-filter"
                    onClick={() => labelSelected!(data[index].rowIdx, 1)}
                  />
                </div>
              );
            },
          },

          ...(isLabeled
            ? [
                {
                  id: 'correct',
                  accessor: ({label, prediction}: {label: number; prediction: number}) => {
                    return label === prediction;
                  },
                  sortType: 'basic',
                  Cell: ({
                    cell: {
                      value,
                      row: {index},
                    },
                  }: {
                    cell: {value: boolean; row: {index: number}};
                  }) => {
                    return data[index].label != null ? (
                      <SlIcon
                        className={`${styles.predictionIcon} ${
                          value ? styles.correct : styles.incorrect
                        }`}
                        name={value ? 'check-square' : 'exclamation-square'}
                      ></SlIcon>
                    ) : (
                      <></>
                    );
                  },
                },
              ]
            : []),
        ],
        [examples, rowIdxFilter, extraColumns]
      ),
      data,
      initialState: initialState,
    },
    useSortBy
  );

  // Compute the sizes of the rows dynamically as a function of the content.
  const sizeMap = React.useRef<{[idx: number]: number}>({});
  const listRef = React.useRef<List>(null);
  const setSize = React.useCallback((index: number, size: number) => {
    sizeMap.current = {...sizeMap.current, [index]: size};
    listRef.current!.resetAfterIndex(index);
  }, []);
  const getSize = (index: number) => sizeMap.current[index] || 50;

  const RenderRow = React.useCallback(
    ({index, style}: {index: number; style: React.CSSProperties}) => {
      const row = rows[index];
      prepareRow(row);

      const rowRef = React.useRef<HTMLDivElement>(null);
      return (
        <div
          ref={rowRef}
          key={`${index}`}
          style={style}
          className={data[row.index].label != null ? 'bg-slate-50' : ''}
        >
          <VariableHeightRow index={index} setSize={setSize}>
            <>
              {row.cells.map((cell) => {
                const cellClasses = [styles.cell];
                if (COLUMN_ID_CELL_CLASS_MAP[cell.column.id] != null) {
                  cellClasses.push(COLUMN_ID_CELL_CLASS_MAP[cell.column.id]);
                }
                // TODO(nsthorat): Figure this out...
                if (cell.column.id != 'text') {
                  cellClasses.push('text-center');
                }
                return (
                  <div {...cell.getCellProps()} className={`${cellClasses.join(' ')}`}>
                    {cell.render('Cell')}
                  </div>
                );
              })}
            </>
          </VariableHeightRow>
        </div>
      );
    },
    [prepareRow, rows]
  );

  const accuracy =
    isLabeled && numLabeledExamples > 0 ? ((100 * correct) / numLabeledExamples).toFixed(2) : null;
  return (
    <div className="flex flex-col w-full">
      <p className="text-lg mt-8">{title}</p>
      <p className="text-sm">{accuracy != null ? `Accuracy: ${accuracy}%` : ''}</p>
      <div>
        <SlRadioGroup
          name="data-view"
          value={filterView}
          onSlChange={(e) => setFilterView((e.target as HTMLInputElement).value as FILTER_VIEW)}
        >
          <SlRadioButton value="all">All ({numTotalExamples})</SlRadioButton>
          <SlRadioButton value="labeled">Labeled ({numLabeledExamples})</SlRadioButton>
          <SlRadioButton value="unlabeled">Unlabeled ({numUnlabeledExamples})</SlRadioButton>
        </SlRadioGroup>
      </div>
      <div className={`${styles.table} w-full`}>
        <div className="w-full overflow-hidden">
          <div {...getTableProps()}>
            <div className={`${styles.header} ${styles.row} bg-slate-100 w-full`}>
              {headerGroups.map((headerGroup) => (
                <div {...headerGroup.getHeaderGroupProps()} className={`flex w-full`}>
                  {headerGroup.headers.map((column) => {
                    const cellClasses = [styles.cell];
                    if (COLUMN_ID_CELL_CLASS_MAP[column.id] != null) {
                      cellClasses.push(COLUMN_ID_CELL_CLASS_MAP[column.id]);
                    }
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    const icon = (column as any).isSorted
                      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        (column as any).isSortedDesc
                        ? 'sort-down'
                        : 'sort-down-alt'
                      : '';
                    return (
                      <div
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        {...column.getHeaderProps((column as any).getSortByToggleProps())}
                        className={`${cellClasses.join(' ')}`}
                      >
                        {column.render('Header')}
                        <div className={`text-xl mx-2 ${icon === '' ? 'hidden' : ''}`}>
                          <SlIcon name={icon}></SlIcon>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            <div {...getTableBodyProps()} className={styles.tableContent}>
              <List
                ref={listRef}
                itemSize={getSize}
                height={tableHeightPx || TABLE_HEIGHT_PX}
                itemCount={rows.length}
                width={'100%'}
              >
                {RenderRow}
              </List>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

interface VariableHeightRowProps {
  index: number;
  setSize: (index: number, height: number) => void;
  children: JSX.Element;
}
// The job of this component is to just measure the height of the row for the react table
// virtualizer, and use it to set the dynamic size of the row after computing the real size.
export const VariableHeightRow = React.memo(function Row({
  index,
  setSize,
  children,
}: VariableHeightRowProps): JSX.Element {
  const rowRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (rowRef.current != null) {
      setSize(index, rowRef.current.getBoundingClientRect().height);
    }
  }, [setSize, index]);

  return (
    <div ref={rowRef} className={`${styles.row} ${styles.statusRow}`}>
      {children}
    </div>
  );
});
interface LabelProps {
  labelId: number | null;
  labels: {[labelId: number]: string};
  onLabelChange: (labelId: number) => void;
}

export const Label = React.memo(function Label({
  labelId,
  labels,
  onLabelChange,
}: LabelProps): JSX.Element {
  const [focused, setFocused] = React.useState(false);

  const selectChanged = (e: Event) => {
    onLabelChange(Number((e.target as HTMLInputElement).value));
    setFocused(false);
  };

  const selectMenuCloses = () => {
    if (labelId != null && labelId >= 0) {
      setFocused(false);
    }
  };

  const showSelect = (labelId != null && labelId < 0) || focused;
  return (
    <>
      <div className={showSelect ? '' : 'hidden'}>
        <SlSelect
          open={focused}
          className={styles.selectLabel}
          size="small"
          hoist
          onSlHide={() => selectMenuCloses()}
          placeholder="Select label"
          onSlChange={(e) => selectChanged(e)}
          value={labelId == null ? NO_LABEL : labelId.toString()}
        >
          {Object.entries(labels).map(([labelId, label]) => (
            <SlOption key={labelId} value={labelId.toString()}>
              {label}
            </SlOption>
          ))}
        </SlSelect>
      </div>

      <div className={`flex ${showSelect ? 'hidden' : ''}`} onClick={() => setFocused(true)}>
        <div
          className={styles.labelPill}
          style={{background: labelId == null ? NO_LABEL_COLOR : LABEL_COLORS[labelId]}}
        >
          {labelId == null ? NO_LABEL : labels[labelId]}
        </div>
      </div>
    </>
  );
});

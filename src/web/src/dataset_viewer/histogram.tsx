import {SlSpinner} from '@shoelace-style/shoelace/dist/react';
import * as React from 'react';
import {VegaLite} from 'react-vega';
import {compile, Config, TopLevelSpec} from 'vega-lite';
import {Path} from '../schema';
import {useSelectGroupsQuery} from '../store/api_dataset';
import {renderError} from '../utils';

const BAR_COUNT_LABEL = 'count';
const BAR_VALUE_LABEL = 'value';
const MAX_GROUPS = 1000;
const BAR_COLOR = 'rgb(163,191,250)'; // Light indigo.
const LABEL_COLOR = 'rgb(45,55,72)'; // Dark gray.

export interface HistogramProps {
  leafPath: Path;
  namespace: string;
  datasetName: string;
  bins?: number[];
}

export const Histogram = React.memo(function Histogram({
  leafPath,
  namespace,
  datasetName,
  bins,
}: HistogramProps): JSX.Element {
  // Fetch groups from database.
  const {
    isFetching,
    error,
    currentData: groupsResult,
  } = useSelectGroupsQuery({namespace, datasetName, options: {leaf_path: leafPath, bins}});
  if (isFetching) {
    return <SlSpinner />;
  }
  if (error) {
    return renderError(error);
  }
  if (groupsResult == null) {
    return <div className="error">Groups result was null</div>;
  }
  if (groupsResult.length > MAX_GROUPS) {
    return (
      <div className="error">
        Too many groups {groupsResult.length}. Max is {MAX_GROUPS}
      </div>
    );
  }
  const histogramData = groupsResult.map((row) => {
    return {
      [BAR_VALUE_LABEL]: row[0],
      [BAR_COUNT_LABEL]: row[1],
    };
  });

  const spec: TopLevelSpec = {
    layer: [
      {
        mark: {type: 'bar', color: BAR_COLOR},
        encoding: {
          x: {
            field: BAR_COUNT_LABEL,
            type: 'quantitative',
            title: '',
            axis: {ticks: false, domain: false, grid: false, values: []},
          },
        },
      },
      {
        mark: {
          type: 'text',
          align: 'left',
          baseline: 'middle',
          dx: 3,
          color: LABEL_COLOR,
        },
        encoding: {
          text: {field: BAR_COUNT_LABEL},
          x: {value: 0},
        },
      },
    ],
    encoding: {
      y: {
        field: BAR_VALUE_LABEL,
        sort: null,
        type: 'ordinal',
        title: '',
        axis: {
          ticks: false,
          domain: false,
          grid: false,
          labelPadding: 130,
          labelAlign: 'left',
          labelFontSize: 14,
          labelColor: LABEL_COLOR,
          labelLimit: 120,
        },
      },
      tooltip: [{field: BAR_VALUE_LABEL}, {field: BAR_COUNT_LABEL}],
    },
    config: {
      view: {
        stroke: 'transparent',
      },
    },
    data: {name: 'table'},
  };

  const barData = {
    table: histogramData,
  };
  const config: Config = {
    bar: {
      orient: 'horizontal',
    },
  };
  const vegaSpec = compile(spec, {config}).spec;
  return <VegaLite spec={vegaSpec} data={barData} actions={false} />;
});

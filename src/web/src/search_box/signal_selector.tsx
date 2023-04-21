import {JSONSchema7} from 'json-schema';
import * as React from 'react';
import {useParams} from 'react-router-dom';
import {SignalInfo} from '../../fastapi_client';
import {useGetSignalsQuery} from '../store/api_signal';
import {renderQuery} from '../utils';
import {Item} from './item_selector';

export function SignalSelector({onSelect}: {onSelect: (signal: SignalInfo) => void}) {
  const {namespace, datasetName} = useParams<{namespace: string; datasetName: string}>();
  if (namespace == null || datasetName == null) {
    throw new Error('Invalid route');
  }
  const query = useGetSignalsQuery();
  return renderQuery(query, (signals) => {
    return (
      <>
        {signals.map((signal) => {
          const jsonSchema = signal.json_schema as JSONSchema7;
          return (
            <Item key={signal.name} onSelect={() => onSelect(signal)}>
              <div className="flex w-full justify-between">
                <div className="truncate">{signal.name}</div>
                <div className="truncate">{jsonSchema.description}</div>
              </div>
            </Item>
          );
        })}
      </>
    );
  });
}

import { SignalsService, type SignalInfo } from '$lilac';
import { createApiQuery } from './apiUtils';

const SIGNALS_TAG = 'signals';

// Strongly typed version of SignalInfo
// https://github.com/lilacai/lilac/issues/141
export type LilacSignalInfo = Omit<SignalInfo, 'json_schema'> & {
  json_schema: {
    title?: string;
    description?: string;
    type?: string;
    properties?: {
      [key: string]: {
        type?: string;
        title?: string;
        description?: string;
        default?: string;
      };
    };
    required?: string[];
  };
};

export const useGetSignalsQuery = createApiQuery(SignalsService.getSignals, SIGNALS_TAG, {
  select: (res) => res as LilacSignalInfo[]
});

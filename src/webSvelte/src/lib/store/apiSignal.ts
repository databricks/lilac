import {SignalsService, type SignalInfoWithTypedSchema} from '$lilac';
import {createApiQuery} from './apiUtils';

const SIGNALS_TAG = 'signals';

export const useGetSignalsQuery = createApiQuery(
  SignalsService.getSignals as () => Promise<SignalInfoWithTypedSchema[]>,
  SIGNALS_TAG
);

import {SignalsService, type SignalInfoWithTypedSchema} from '$lilac';
import {createApiQuery} from './queryUtils';

const SIGNALS_TAG = 'signals';

export const querySignals = createApiQuery(
  SignalsService.getSignals as () => Promise<SignalInfoWithTypedSchema[]>,
  SIGNALS_TAG
);

export const queryEmbeddings = createApiQuery(
  SignalsService.getEmbeddings as () => Promise<SignalInfoWithTypedSchema[]>,
  SIGNALS_TAG
);

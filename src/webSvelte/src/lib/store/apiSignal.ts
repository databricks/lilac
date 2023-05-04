import { SignalsService } from '$lilac';
import { createApiQuery } from './apiUtils';

const SIGNALS_TAG = 'signals';

export const useGetSignalsQuery = createApiQuery(SignalsService.getSignals, SIGNALS_TAG);

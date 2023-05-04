import { SignalsService } from '../fastapi_client';
import { createApiQuery } from './apiUtils';

const SIGNALS_TAG = 'signals';

export const useGetSignalsQuery = createApiQuery(SignalsService.getSignals, SIGNALS_TAG);

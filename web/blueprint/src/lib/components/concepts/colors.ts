import type {OverallScore} from '$lilac';

export const scoreToColor: Record<OverallScore, string> = {
  not_good: 'text-red-600',
  ok: 'text-yellow-600',
  good: 'text-green-600',
  very_good: 'text-blue-600',
  great: 'text-purple-600'
};

export const scoreToText: Record<OverallScore, string> = {
  not_good: 'Not good',
  ok: 'OK',
  good: 'Good',
  very_good: 'Very good',
  great: 'Great'
};

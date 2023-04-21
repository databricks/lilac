import {EnrichmentType, Field} from '../../fastapi_client';
import {Path} from '../schema';

export function getLeafsByEnrichmentType(leafs: [Path, Field][], enrichmentType?: EnrichmentType) {
  if (enrichmentType == null) {
    return leafs;
  }
  if (enrichmentType !== 'text') {
    throw new Error(`Unsupported enrichment type: ${enrichmentType}`);
  }
  return leafs.filter(([path, field]) => leafMatchesEnrichmentType([path, field], enrichmentType));
}

export function leafMatchesEnrichmentType(
  [, field]: [Path, Field],
  enrichmentType: EnrichmentType
): boolean {
  if (enrichmentType === 'text' && ['string', 'string_span'].includes(field.dtype!)) {
    return true;
  }
  return false;
}

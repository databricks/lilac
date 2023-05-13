import {InputType, Field} from '../../fastapi_client';
import {Path} from '../schema';

export function getLeafsByInputType(leafs: [Path, Field][], inputType?: InputType) {
  if (inputType == null) {
    return leafs;
  }
  if (inputType !== 'text') {
    throw new Error(`Unsupported input type: ${inputType}`);
  }
  return leafs.filter(([path, field]) => leafMatchesInputType([path, field], inputType));
}

export function leafMatchesInputType([, field]: [Path, Field], inputType: InputType): boolean {
  if (inputType === 'text' && ['string', 'string_span'].includes(field.dtype!)) {
    return true;
  }
  return false;
}

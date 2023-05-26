/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

/**
 * Sensitivity levels of a concept.
 *
 * The sensitivity of concept models vary as a function of how powerful the embedding is, and how
 * complicated or subtle the concept is. Therefore, we provide a way to control the sensitivity of
 * the concept model.
 *
 * - `VERY_SENSITIVE` will fire "True" more often and therefore introduce more false positives
 * (will add things that don't fit in the concept).
 * - `NOT_SENSITIVE` will fire "True" less often and therefore introduce more false negatives
 * (misses things that fit in the concept).
 */
export type Sensitivity = 'not sensitive' | 'balanced' | 'sensitive' | 'very sensitive';

/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Concept } from '../models/Concept';
import type { ConceptUpdate } from '../models/ConceptUpdate';
import type { ScoreBody } from '../models/ScoreBody';
import type { ScoreResponse } from '../models/ScoreResponse';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class ConceptsService {

    /**
     * Get Concept
     * Get a concept from a database.
     * @param namespace
     * @param conceptName
     * @returns Concept Successful Response
     * @throws ApiError
     */
    public static getConcept(
        namespace: string,
        conceptName: string,
    ): CancelablePromise<Concept> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/{namespace}/{concept_name}',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Edit Concept
     * Edit a concept in the database.
     * @param namespace
     * @param conceptName
     * @param requestBody
     * @returns Concept Successful Response
     * @throws ApiError
     */
    public static editConcept(
        namespace: string,
        conceptName: string,
        requestBody: ConceptUpdate,
    ): CancelablePromise<Concept> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/concepts/{namespace}/{concept_name}',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Get Concept Model
     * Get a concept model from a database.
     * @param namespace
     * @param conceptName
     * @param embeddingName
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getConceptModel(
        namespace: string,
        conceptName: string,
        embeddingName: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/{namespace}/{concept_name}/{embedding_name}',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
                'embedding_name': embeddingName,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Score
     * Score examples along the specified concept.
     * @param namespace
     * @param conceptName
     * @param embeddingName
     * @param requestBody
     * @returns ScoreResponse Successful Response
     * @throws ApiError
     */
    public static score(
        namespace: string,
        conceptName: string,
        embeddingName: string,
        requestBody: ScoreBody,
    ): CancelablePromise<ScoreResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/concepts/{namespace}/{concept_name}/{embedding_name}/score',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
                'embedding_name': embeddingName,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

}

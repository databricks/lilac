/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Concept } from '../models/Concept';
import type { ConceptInfo } from '../models/ConceptInfo';
import type { ConceptModelResponse } from '../models/ConceptModelResponse';
import type { ConceptUpdate } from '../models/ConceptUpdate';
import type { CreateConceptOptions } from '../models/CreateConceptOptions';
import type { MergeConceptDraftOptions } from '../models/MergeConceptDraftOptions';
import type { ScoreBody } from '../models/ScoreBody';
import type { ScoreResponse } from '../models/ScoreResponse';

import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';

export class ConceptsService {

    /**
     * Get Concepts
     * List the concepts.
     * @returns ConceptInfo Successful Response
     * @throws ApiError
     */
    public static getConcepts(): CancelablePromise<Array<ConceptInfo>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/',
        });
    }

    /**
     * Get Concept
     * Get a concept from a database.
     * @param namespace
     * @param conceptName
     * @param draft
     * @returns Concept Successful Response
     * @throws ApiError
     */
    public static getConcept(
        namespace: string,
        conceptName: string,
        draft?: ('main' | string),
    ): CancelablePromise<Concept> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/{namespace}/{concept_name}',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
            },
            query: {
                'draft': draft,
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
     * Create Concept
     * Edit a concept in the database.
     * @param requestBody
     * @returns Concept Successful Response
     * @throws ApiError
     */
    public static createConcept(
        requestBody: CreateConceptOptions,
    ): CancelablePromise<Concept> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/concepts/create',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }

    /**
     * Merge Concept Draft
     * Merge a draft in the concept into main.
     * @param namespace
     * @param conceptName
     * @param requestBody
     * @returns Concept Successful Response
     * @throws ApiError
     */
    public static mergeConceptDraft(
        namespace: string,
        conceptName: string,
        requestBody: MergeConceptDraftOptions,
    ): CancelablePromise<Concept> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/concepts/{namespace}/{concept_name}/merge_draft',
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
     * @param syncModel
     * @returns ConceptModelResponse Successful Response
     * @throws ApiError
     */
    public static getConceptModel(
        namespace: string,
        conceptName: string,
        embeddingName: string,
        syncModel: boolean = false,
    ): CancelablePromise<ConceptModelResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/{namespace}/{concept_name}/{embedding_name}',
            path: {
                'namespace': namespace,
                'concept_name': conceptName,
                'embedding_name': embeddingName,
            },
            query: {
                'sync_model': syncModel,
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

    /**
     * Generate Examples
     * Generate positive examples for a given concept using an LLM model.
     * @param description
     * @returns string Successful Response
     * @throws ApiError
     */
    public static generateExamples(
        description: string,
    ): CancelablePromise<Array<string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/concepts/generate_examples',
            query: {
                'description': description,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }

}

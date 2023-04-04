// Request interfaces.
export interface ModelOptions {
  username?: string;
  name?: string;
}

export interface CreateModelOptions {
  username: string;
  name: string;
  description: string;
}

export interface SaveModelOptions {
  username: string;
  name: string;
  labeled_data: LabeledExample[];
}

export interface AddExamplesOptions {
  username: string;
  name: string;
  examples: Array<{text: string; label: number}>;
}

export interface SearchExamplesOptions {
  username: string;
  modelName: string;
  query: string;
}

// Response interfaces.
export interface CreateModelResponse {
  name: string;
}

// Database interfaces.
export interface UserInfo {
  id: number;
  username: string;
  name: string;
  date_joined: string;
}

export interface ModelInfo {
  id: number;
  username: string;
  name: string;
  description: string;
  date_created: string;
}

export interface ListModelsResponse {
  models: ModelInfo[];
}

export interface DatasetRow {
  text: string;
  prediction: number;

  // Extra sortable metadata.
  metadata: {[columnName: string]: string | number};
}

export interface LabeledExample {
  row_idx: number;
  label: number;
}

export interface Dataset {
  data: DatasetRow[];
  labeled_data: LabeledExample[];
}

export interface AddDatasetOptions {
  username: string;
  model_name: string;

  hf_dataset: string;
  hf_split: string;
  hf_text_field: string;
}

export interface LoadModelResponse {
  dataset?: Dataset;
  has_data: boolean;
}

export interface SearchExamplesResponse {
  row_results: Array<{row_idx: number; similarity: number}>;
}

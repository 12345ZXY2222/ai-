import client from './client';

export interface LLMExperimentPaperRecord {
  id: string;
  title: string;
  source: string;
  file_name?: string;
  content_preview?: string;
  created_at: number;
}

export interface LLMExperimentUploadPaperResponse {
  paper: LLMExperimentPaperRecord;
}

export interface LLMExperimentBuildRequest {
  paper_id?: string;
  paper_text?: string;
  requirements: string;
  experiment_goal?: string;
  constraints?: string;
  save_simulation?: boolean;
}

export interface LLMExperimentBuildResponse {
  session_id: string;
  paper_id?: string;
  experiment_design: string;
  analysis_thinking: string;
  simulation_draft: Record<string, any>;
  simulation_reviewed: Record<string, any>;
  checker_notes: string;
  analysis_code_seed: string;
  created_agent_ids: string[];
  created_at: number;
}

export interface LLMExperimentAnalyzeRunRequest {
  session_id?: string;
  paper_id?: string;
  requirements: string;
  experiment_goal?: string;
  analysis_thinking?: string;
  analysis_injected_requirements?: string;
  analysis_file_id?: string;
  run_history: Record<string, any>[];
  final_world_state: Record<string, any>;
}

export interface LLMExperimentAnalyzeRunResponse {
  analysis_code: string;
  analysis_stdout: string;
  analysis_result: Record<string, any>;
  conclusion: string;
}

export interface LLMExperimentAnalysisFileRecord {
  id: string;
  file_name: string;
  extracted_preview?: string;
  created_at: number;
}

export interface LLMExperimentUploadAnalysisFileResponse {
  file: LLMExperimentAnalysisFileRecord;
}

export interface LLMExperimentComparisonReportRequest {
  session_id?: string;
  paper_id?: string;
  requirements: string;
  compare_requirements?: string;
  analysis_result?: Record<string, any>;
  analysis_conclusion?: string;
}

export interface LLMExperimentComparisonReportResponse {
  report: string;
}

export interface LLMExperimentSessionRecord {
  id: string;
  user_id: string;
  paper_id?: string;
  paper_title?: string;
  requirements: string;
  experiment_goal?: string;
  experiment_design: string;
  analysis_thinking: string;
  simulation_reviewed: Record<string, any>;
  analysis_code_seed: string;
  checker_notes: string;
  latest_analysis?: {
    analysis_code: string;
    analysis_stdout: string;
    analysis_result: Record<string, any>;
    conclusion: string;
    created_at?: number;
  };
  latest_analysis_file_id?: string;
  latest_analysis_injected_requirements?: string;
  latest_comparison_report?: string;
  latest_compare_requirements?: string;
  created_agent_ids: string[];
  created_at: number;
}

export const uploadExperimentPaper = async (file: File): Promise<LLMExperimentUploadPaperResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await client.post<LLMExperimentUploadPaperResponse>('/llm-experiments/papers/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  });
  return res.data;
};

export const listExperimentPapers = async (): Promise<LLMExperimentPaperRecord[]> => {
  const res = await client.get<LLMExperimentPaperRecord[]>('/llm-experiments/papers');
  return res.data;
};

export const solveExperimentPipeline = async (
  payload: LLMExperimentBuildRequest,
): Promise<LLMExperimentBuildResponse> => {
  const res = await client.post<LLMExperimentBuildResponse>('/llm-experiments/cluster/solve', payload, {
    timeout: 900000,
  });
  return res.data;
};

export const analyzeExperimentRun = async (
  payload: LLMExperimentAnalyzeRunRequest,
): Promise<LLMExperimentAnalyzeRunResponse> => {
  const res = await client.post<LLMExperimentAnalyzeRunResponse>('/llm-experiments/cluster/analyze-run', payload, {
    timeout: 600000,
  });
  return res.data;
};

export const uploadAnalysisDataFile = async (file: File): Promise<LLMExperimentUploadAnalysisFileResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await client.post<LLMExperimentUploadAnalysisFileResponse>('/llm-experiments/analysis-files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  });
  return res.data;
};

export const generateComparisonReport = async (
  payload: LLMExperimentComparisonReportRequest,
): Promise<LLMExperimentComparisonReportResponse> => {
  const res = await client.post<LLMExperimentComparisonReportResponse>('/llm-experiments/cluster/comparison-report', payload, {
    timeout: 600000,
  });
  return res.data;
};

export const listExperimentSessions = async (limit = 20): Promise<LLMExperimentSessionRecord[]> => {
  const res = await client.get<LLMExperimentSessionRecord[]>('/llm-experiments/sessions', {
    params: { limit },
  });
  return res.data;
};

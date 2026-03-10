from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class LLMExperimentPaperRecord(BaseModel):
    id: str
    title: str
    source: str = "upload"
    file_name: Optional[str] = None
    content_preview: Optional[str] = None
    created_at: float


class LLMExperimentUploadPaperResponse(BaseModel):
    paper: LLMExperimentPaperRecord


class LLMExperimentDesignRequest(BaseModel):
    paper_id: Optional[str] = None
    paper_text: Optional[str] = None
    requirements: str
    experiment_goal: Optional[str] = None
    constraints: Optional[str] = None


class LLMExperimentDesignResponse(BaseModel):
    experiment_design: str
    analysis_thinking: str


class LLMExperimentBuildRequest(BaseModel):
    paper_id: Optional[str] = None
    paper_text: Optional[str] = None
    requirements: str
    experiment_goal: Optional[str] = None
    constraints: Optional[str] = None
    save_simulation: bool = True


class LLMExperimentBuildResponse(BaseModel):
    session_id: str
    paper_id: Optional[str] = None
    experiment_design: str
    analysis_thinking: str
    simulation_draft: Dict[str, Any]
    simulation_reviewed: Dict[str, Any]
    checker_notes: str
    analysis_code_seed: str
    created_agent_ids: List[str] = []
    created_at: float


class LLMExperimentAnalyzeRunRequest(BaseModel):
    session_id: Optional[str] = None
    paper_id: Optional[str] = None
    requirements: str
    experiment_goal: Optional[str] = None
    analysis_thinking: Optional[str] = None
    analysis_injected_requirements: Optional[str] = None
    analysis_file_id: Optional[str] = None
    run_history: List[Dict[str, Any]] = []
    final_world_state: Dict[str, Any] = {}


class LLMExperimentAnalyzeRunResponse(BaseModel):
    analysis_code: str
    analysis_stdout: str
    analysis_result: Dict[str, Any]
    conclusion: str


class LLMExperimentAnalysisFileRecord(BaseModel):
    id: str
    file_name: str
    extracted_preview: Optional[str] = None
    created_at: float


class LLMExperimentUploadAnalysisFileResponse(BaseModel):
    file: LLMExperimentAnalysisFileRecord


class LLMExperimentComparisonReportRequest(BaseModel):
    session_id: Optional[str] = None
    paper_id: Optional[str] = None
    requirements: str
    compare_requirements: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None
    analysis_conclusion: Optional[str] = None


class LLMExperimentComparisonReportResponse(BaseModel):
    report: str


class LLMExperimentSessionRecord(BaseModel):
    id: str
    user_id: str
    paper_id: Optional[str] = None
    paper_title: Optional[str] = None
    requirements: str
    experiment_goal: Optional[str] = None
    experiment_design: str
    analysis_thinking: str
    simulation_reviewed: Dict[str, Any]
    analysis_code_seed: str
    checker_notes: str
    latest_analysis: Optional[Dict[str, Any]] = None
    latest_analysis_file_id: Optional[str] = None
    latest_analysis_injected_requirements: Optional[str] = None
    latest_comparison_report: Optional[str] = None
    latest_compare_requirements: Optional[str] = None
    created_agent_ids: List[str] = []
    created_at: float


class LLMExperimentAnalysisRecord(BaseModel):
    id: str
    user_id: str
    session_id: Optional[str] = None
    paper_id: Optional[str] = None
    requirements: str
    analysis_code: str
    analysis_stdout: str
    analysis_result: Dict[str, Any]
    conclusion: str
    created_at: float

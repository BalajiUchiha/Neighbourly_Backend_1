from pydantic import BaseModel
from typing import Optional, List

class AIRefineRequest(BaseModel):
    raw_input: str
    retry_reason: Optional[str] = None
    previous_result: Optional[dict] = None
    preferred_language: Optional[str] = "english"

class AIRefineResult(BaseModel):
    title: str
    description: str
    task_type: str
    post_category: str
    job_nature: str
    urgency_tag: str
    pay_per_person: Optional[int] = None
    workers_needed: int = 1
    no_exp_needed: bool = False
    work_date: Optional[str] = None
    work_time_slot: Optional[str] = None
    area_name: Optional[str] = None
    tags: List[str] = []
    confidence_note: Optional[str] = None

class PostCreateRequest(BaseModel):
    ai_result: dict
    additional_details: dict
    raw_input: str
    input_method: str
    ai_generated: bool = True

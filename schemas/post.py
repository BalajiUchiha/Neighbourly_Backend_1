from pydantic import BaseModel, Field
from typing import Optional, List

class AIRefineRequest(BaseModel):
    raw_input: str
    retry_reason: Optional[str] = None
    previous_result: Optional[dict] = None
    preferred_language: Optional[str] = "english"

class AIRefineResult(BaseModel):
    title: str = Field(description="Short clear task title, max 8 words")
    description: str = Field(description="Clean 1-2 sentence description of the task")
    task_type: str = Field(description="One of: farming, lifting, cleaning, driving, cooking, plumbing, electrical, carpentry, event_setup, security, shifting, other")
    post_category: str = Field(description="'paid' if any payment mentioned, 'volunteer' if free or community work")
    job_nature: str = Field(description="'full_day', 'part_time', 'one_day', 'ongoing', or 'helper_needed'")
    urgency_tag: str = Field(description="'today', 'tomorrow', 'this_week', or 'flexible'")
    pay_per_person: Optional[int] = Field(default=None, description="Integer in rupees if mentioned")
    workers_needed: int = Field(default=1, description="Number of workers needed")
    no_exp_needed: bool = Field(default=False, description="True if no skill required, False if skill needed")
    work_date: Optional[str] = Field(default=None, description="ISO date string if specific date mentioned")
    work_time_slot: Optional[str] = Field(default=None, description="'morning', 'afternoon', or 'evening'")
    area_name: Optional[str] = Field(default=None, description="Area or locality name if mentioned")
    tags: List[str] = Field(default=[], description="Array of 2-4 relevant short tags")
    confidence_note: Optional[str] = Field(default=None, description="Short note if anything was unclear, else null")

class PostCreateRequest(BaseModel):
    ai_result: dict
    additional_details: dict
    raw_input: str
    input_method: str
    ai_generated: bool = True

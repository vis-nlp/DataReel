from typing import TypedDict, Optional, Dict, List

class VideoState(TypedDict):
    # INPUTS 
    sample_id: str
    data_table: str
    transcript: str
    duration: int
    intent: str

    # ARTIFACTS 
    plan: Optional[str]           
    plan_critique: Optional[str]  
    html: Optional[str]           
    
    # FEEDBACK 
    visual_feedback: Optional[str] 

    # RAW RESPONSES
    director_raw: Optional[str]
    plan_critic_raw: Optional[str]
    video_critic_raw: Optional[str]

    # CONTROL 
    iterations: int              
    max_iterations: int           
    
    approved: bool
from pydantic import BaseModel, Field

class CRMTicket(BaseModel):
    """Structured CRM Ticket to be captured by the AI agent and saved to MongoDB."""
    
    customer_name: str = Field(description="Name of the prospective learner (if known, otherwise 'Unknown'). Write in Arabic.")
    contact_info: str = Field(description="Phone number, WhatsApp, or email. Write exactly as provided.")
    city: str = Field(description="City or country of the user. Write in Arabic.")
    language_dialect: str = Field(description="The Arabic dialect used (e.g., اللهجة المصرية) or English. Write in Arabic.")
    
    products_of_interest: str = Field(description="Specific courses, tracks, or diplomas they are interested in. Keep tech terms (SOC, Python, etc.) in English.")
    goal: str = Field(description="Their learning goal or career motivation. Write in Arabic.")
    current_level: str = Field(description="Their current skill level (e.g., مبتدئ, متوسط). Write in Arabic.")
    
    buying_signals: str = Field(description="Lead temperature (hot/warm/cold) and any positive buying signals. Write in Arabic.")
    objections: str = Field(description="Any concerns raised, like price, time, or prerequisites. Write in Arabic.")
    
    arabic_summary: str = Field(description="A short, professional summary of the conversation. Must be in Arabic.")
    next_action: str = Field(description="Recommended next step for the human sales rep. Must be in Arabic.")
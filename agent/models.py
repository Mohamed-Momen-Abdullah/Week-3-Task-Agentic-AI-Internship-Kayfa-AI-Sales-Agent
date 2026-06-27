from pydantic import BaseModel, Field

class CRMTicket(BaseModel):
    """Structured CRM Ticket to be captured by the AI agent and saved to MongoDB."""
    
    model_config = {'title': 'CRMTicket'}

    customer_name: str = Field(default="غير معروف", description="Name of the prospective learner (if known, otherwise 'غير معروف'). Write in Arabic.")
    contact_info: str = Field(description="Phone number, WhatsApp, or email. Write exactly as provided.")
    city: str = Field(default="غير معروف", description="City or country of the user. Write in Arabic.")
    language_dialect: str = Field(default="غير معروف", description="The Arabic dialect used (e.g., اللهجة المصرية) or English. Write in Arabic.")
    
    products_of_interest: str = Field(default="غير معروف", description="Specific courses, tracks, or diplomas they are interested in. Keep tech terms (SOC, Python, etc.) in English.")
    goal: str = Field(default="غير معروف", description="Their learning goal or career motivation. Write in Arabic.")
    current_level: str = Field(default="غير معروف", description="Their current skill level (e.g., مبتدئ, متوسط). Write in Arabic.")
    
    buying_signals: str = Field(default="دافئ", description="Lead temperature (hot/warm/cold) and any positive buying signals. Write in Arabic.")
    objections: str = Field(default="لا يوجد", description="Any concerns raised, like price, time, or prerequisites. Write in Arabic.")
    
    arabic_summary: str = Field(default="لا يوجد", description="A short, professional summary of the conversation. Must be in Arabic.")
    next_action: str = Field(default="المتابعة والتواصل", description="Recommended next step for the human sales rep. Must be in Arabic.")
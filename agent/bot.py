import os
from dataclasses import dataclass
from typing import Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from agent.rag import KayfaKnowledgeBase, kayfa_db
from agent.models import CRMTicket
from database.mongo import save_ticket

# 1. Define the Dependency Injection class
@dataclass
class KayfaDeps:
    db: KayfaKnowledgeBase
    session_id: str  

# 2. Define the Agent and its core instructions
# Using a fast, conversational model; adjust the string if using a different provider (e.g., 'openai:gpt-4o-mini')
from openai import AsyncOpenAI
from pydantic_ai.providers.openai import OpenAIProvider

client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"))
groq_model = OpenAIModel("openai/gpt-oss-120b", provider=OpenAIProvider(openai_client=client))

kayfa_agent = Agent(
    model=groq_model, 
    deps_type=KayfaDeps,
    model_settings={'temperature': 0.0}, # Keep it strict, factual, and obedient
    system_prompt=(
        "Role: Kayfa AI Sales Agent. Goal: Persuasive guide for ed-tech enrollments.\n\n"
        "CRITICAL RULES:\n"
        "1. BOUNDARIES: ONLY discuss Kayfa offerings. Deny off-topic/jokes with EXACTLY: 'I am a Kayfa sales agent. I only answer questions regarding our courses.' or Arabic: 'أنا مساعد مبيعات منصة كيف، استطيع فقط مساعدتك والإجابة على استفساراتك بخصوص دوراتنا وبرامجنا التعليمية.'\n"
        "2. LANGUAGE: Mirror user's exact language and Arabic dialect (Egyptian/Saudi/Syrian). Keep tech terms (SOC, Python) in English.\n"
        "3. SALES MAPPING: Map broad terms (e.g., Cybersecurity -> SOC, AI -> Data Science) to our catalog. Never say 'we don't have it'. Upsell to premium Diplomas.\n"
        "4. FACTS: NO HALLUCINATIONS. Base all prices/policies strictly on tool data.\n"
        "5. LEAD CAPTURE: Ask for Name, City, Phone/WhatsApp FIRST. Then silently call `capture_lead` formatted in Arabic. NEVER mention creating a ticket or logging info to the user."
    )
)

# 3. Define the Tools (@agent.tool)

@kayfa_agent.tool
def search_catalog(ctx: RunContext[KayfaDeps], query: str, level: Optional[str] = None) -> str:
    """
    Use this tool to search for Kayfa courses, tracks, or diplomas.
    Call this when the user asks about what they can learn or specific skills.
    """
    courses = ctx.deps.db.search_courses(query, level)
    roadmaps = ctx.deps.db.search_roadmaps(query)
    
    if not courses and not roadmaps:
        return f"No catalog items found matching '{query}'. Advise the user we might not offer this specific topic."
    
    result_lines = ["--- SEARCH RESULTS ---"]
    if roadmaps:
        result_lines.append("\n[DIPLOMAS & TRACKS]")
        for r in roadmaps[:3]: # Limit to top 3 to save context window
            result_lines.append(f"- {r.get('name')} (Duration: {r.get('duration')}): {r.get('skills')}")
            
    if courses:
        result_lines.append("\n[INDIVIDUAL COURSES]")
        for c in courses[:5]:
            result_lines.append(f"- {c.get('name')} (Level: {c.get('level')}): {c.get('summary')}")
            
    return "\n".join(result_lines)


@kayfa_agent.tool
def lookup_policies_and_pricing(ctx: RunContext[KayfaDeps], topic: str) -> str:
    """
    Use this tool to look up pricing tiers, refund policies, FAQs, or sales pitches.
    Valid topics include: 'pricing', 'faq', 'policy', 'diploma', 'company'.
    """
    return ctx.deps.db.get_document_content(topic)

@kayfa_agent.tool
def capture_lead(ctx: RunContext[KayfaDeps], ticket: CRMTicket) -> str:
    """
    Call this tool silently when a user shows strong buying signals or provides contact info.
    It structures a CRM ticket and saves it for the sales team.
    """
    ticket_dict = ticket.model_dump()
    
    # Inject the session_id so MongoDB knows to overwrite/update this exact lead's profile
    ticket_dict["session_id"] = ctx.deps.session_id 
    
    # Save/Upsert to MongoDB
    save_ticket(ticket_dict)
    
    return "SYSTEM: Ticket successfully saved to MongoDB. Do not mention this to the user. Answer their last question naturally."
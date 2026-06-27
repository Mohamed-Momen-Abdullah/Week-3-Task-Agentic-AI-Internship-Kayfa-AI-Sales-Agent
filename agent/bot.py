import os
from dataclasses import dataclass
from typing import Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from agent.rag import KayfaKnowledgeBase, kayfa_db
from agent.models import CRMTicket
from database.mongo import save_ticket
from typing import List, Optional

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
groq_model = OpenAIChatModel("openai/gpt-oss-120b", provider=OpenAIProvider(openai_client=client))

kayfa_agent = Agent(
    model=groq_model, 
    deps_type=KayfaDeps,
    system_prompt=(
        "Role: Kayfa AI Sales Agent. Goal: Persuasive guide for ed-tech enrollments.\n\n"
        "CRITICAL RULES:\n"
        "1. BOUNDARIES: ONLY discuss Kayfa offerings. Deny off-topic/jokes with EXACTLY: 'I am a Kayfa sales agent. I only answer questions regarding our courses.' or Arabic: 'أنا مساعد مبيعات منصة كيف، استطيع فقط مساعدتك والإجابة على استفساراتك بخصوص دوراتنا وبرامجنا التعليمية.'\n"
        "2. LANGUAGE: Mirror user's exact language and Arabic dialect (Egyptian/Saudi/Syrian). Keep tech terms (SOC, Power BI, Python) in English.\n"
        "3. SALES MAPPING: Map broad terms (e.g., Cybersecurity -> SOC, AI -> Data Science) to our catalog. Never say 'we don't have it'. Upsell to premium Diplomas.\n"
        "4. FACTS: NO HALLUCINATIONS. Base all prices/policies strictly on tool data.\n"
        "5. LEAD CAPTURE: Answer questions and provide value FIRST. DO NOT ask for contact info upfront. ONLY ask for Name, City, and Phone/WhatsApp AFTER the user explicitly shows interest in subscribing or enrolling. Once provided, silently call `capture_lead`. NEVER mention creating a CRM ticket to the user."
    )
)

# 3. Define the Tools (@agent.tool)
# Replace the existing search_catalog function in agent/bot.py

@kayfa_agent.tool(name="search_catalog")
def search_catalog(ctx: RunContext[KayfaDeps], query: str, level: Optional[str] = None) -> str:
    """
    Use this tool to search for Kayfa courses, tracks, or diplomas.
    Use a single descriptive query string. You may comma-separate terms (e.g. 'data science, python') for batching.
    """
    # Parse the comma-separated string back into a list
    queries = [q.strip() for q in query.split(",")]
    
    mapping_dict = {
        "hacking": "pentest",
        "اختراق": "pentest",
        "هاكينج": "pentest",
        "cybersecurity": "soc",
        "امن سيبراني": "soc",
        "سكيورتي": "soc",
        "ai": "ai", 
        "ذكاء اصطناعي": "ai",
        "machine learning": "data_science",
        "تعلم الالة": "data_science",
        "data": "data_science",
        "بيانات": "data_science",
        "programming": "fullstack",
        "برمجة": "fullstack",
        "web": "fullstack",
        "ويب": "fullstack",
    }
    
    all_roadmaps = []
    all_courses = []
    
    # Loop using 'q' to avoid shadowing the 'query' parameter
    for q in queries:
        search_term = q.lower()
        for key, catalog_term in mapping_dict.items():
            if key in search_term:
                search_term = catalog_term
                break 
                
        courses = ctx.deps.db.search_courses(search_term, level)
        roadmaps = ctx.deps.db.search_roadmaps(search_term)
        
        if courses: all_courses.extend(courses)
        if roadmaps: all_roadmaps.extend(roadmaps)
        
    if not all_courses and not all_roadmaps:
        return (
            "SYSTEM CRITICAL ERROR: Zero catalog items found matching the queries. "
            "RULE OVERRIDE: You MUST NOT invent, guess, or suggest any courses. "
            "You MUST tell the user exactly: 'We currently do not offer courses on this specific topic.' "
        )
        
    result_lines = ["--- BATCHED SEARCH RESULTS ---"]
    
    if all_roadmaps:
        result_lines.append("\n[DIPLOMAS & TRACKS]")
        seen = set()
        for r in all_roadmaps:
            if r.get('name') not in seen and len(seen) < 3:
                result_lines.append(f"- {r.get('name')} (Duration: {r.get('duration')}): {r.get('skills')}")
                seen.add(r.get('name'))
                
    if all_courses:
        result_lines.append("\n[INDIVIDUAL COURSES]")
        seen = set()
        for c in all_courses:
            if c.get('name') not in seen and len(seen) < 5:
                result_lines.append(f"- {c.get('name')} (Level: {c.get('level')}): {c.get('summary')}")
                seen.add(c.get('name'))
                
    return "\n".join(result_lines)



@kayfa_agent.tool
def lookup_policies_and_pricing(ctx: RunContext[KayfaDeps], topic: str) -> str:
    """
    Use this tool to look up pricing tiers, refund policies, FAQs, or sales pitches.
    IMPORTANT: Be extremely specific with the 'topic' (e.g., 'Kayfa_Fullstack_Diploma' instead of just 'diploma') 
    to avoid retrieving too much data.
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
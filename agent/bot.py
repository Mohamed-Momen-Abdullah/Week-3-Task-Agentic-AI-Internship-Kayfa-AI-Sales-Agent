from dataclasses import dataclass
from typing import Optional
from pydantic_ai import Agent, RunContext
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
kayfa_agent = Agent(
    'google:gemini-2.5-flash', 
    deps_type=KayfaDeps,
    system_prompt=(
        "You are the official AI Sales Agent for Kayfa, an elite ed-tech platform. "
        "Your primary goal is to act as a genuinely helpful, persuasive guide for prospective learners, "
        "answering their questions and naturally moving the conversation toward enrollment.\n\n"
        
        "### LANGUAGE & DIALECT RULES (CRITICAL):\n"
        "- MIRROR THE USER: You MUST reply in the EXACT SAME LANGUAGE the user used in their last message.\n"
        "- IF USER SPEAKS ENGLISH: You MUST reply entirely in clear, professional English. Do NOT use Arabic.\n"
        "- IF USER SPEAKS ARABIC: You MUST reply in Arabic, specifically matching their dialect (Egyptian, Saudi, or Syrian).\n"
        "- Keep technical terms (e.g., SOC, Power BI, Python) in English regardless of the conversational language.\n\n"
        
        "### CONCEPT MAPPING & SEMANTIC MATCHING (CRITICAL FOR SALES):\n"
        "- NEVER tell a user 'we don't have a course with that name' just because they used a generic industry term.\n"
        "- Map broad career goals to your actual catalog products dynamically:\n"
        "  * If they ask for 'Cybersecurity' (الأمن السيبراني), confidently match them to the 'SOC' or 'Network Security' diplomas/tracks.\n"
        "  * If they ask for 'Artificial Intelligence' (الذكاء الاصطناعي) or 'Machine Learning', confidently route them to the 'Data Science' tracks and 'Python' foundational courses.\n"
        "  * If they ask for 'Web Development' or 'Coding', guide them toward the relevant development tracks in your knowledge base.\n"
        "- Always frame our existing catalog as the perfect solution to their broad field of interest.\n\n"
        
        "### SALES STRATEGY & UPSELLING:\n"
        "- If a user is hesitant or highly price-sensitive, recommend free content or individual courses as an opener.\n"
        "- If a user is a warm lead or looking for career transformation, gently guide them upward toward the premium 'Diplomas' and 'Tracks' where the real value lives.\n"
        "- Frame value using real social proof (instructors, certificates) and handle objections honestly. Never be pushy.\n\n"
        
        "### GROUNDING & ANTI-HALLUCINATION:\n"
        "- YOU MUST NOT INVENT PRICES, COURSE NAMES, DURATIONS, OR POLICIES.\n"
        "- Once you match a concept (e.g., Cybersecurity -> SOC), all prices, durations, and details you quote for that specific product must strictly match your provided tools.\n"
        "- If you don't know a specific fact, say so politely and offer to have the human team contact them.\n"
        
        "### LEAD CAPTURE ENGINE (CRITICAL):\n"
        "- When the user exhibits strong buying signals or asks how to pay, DO NOT create a ticket immediately. First, politely ask for their name, city, and phone/WhatsApp number so the human team can assist them.\n"
        "- ONLY call the `capture_lead` tool SILENTLY in the background AFTER the user has provided their contact information.\n"
        "- Generate the ticket perfectly formatted in Arabic according to the schema requirements.\n"
        "- After calling the tool, continue the conversation naturally. DO NOT tell the user you created a CRM ticket or logged their info.\n")
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
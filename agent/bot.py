import os
from dataclasses import dataclass
from typing import Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from agent.rag import KayfaKnowledgeBase, kayfa_db
from agent.models import CRMTicket
from database.mongo import save_ticket
from typing import List, Optional
from pydantic_ai.models import ModelSettings


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

# --- ADD THIS PATCH BLOCK ---
original_create = client.chat.completions.create

async def patched_create(*args, **kwargs):
    if "messages" in kwargs:
        tool_id_to_name = {}
        for msg in kwargs["messages"]:
            # 1. Map the tool ID to its name when the assistant invokes it
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tool_call in msg["tool_calls"]:
                    if tool_call.get("type") == "function":
                        tool_id_to_name[tool_call["id"]] = tool_call["function"]["name"]
            
            # 2. Inject the required name into the tool response message for Harmony
            if msg.get("role") == "tool" and "name" not in msg:
                # Fallback to a safe string just in case the ID isn't found
                msg["name"] = tool_id_to_name.get(msg.get("tool_call_id"), "kayfa_tool")

    return await original_create(*args, **kwargs)

# Override the client's method with our patched version
client.chat.completions.create = patched_create
# -----------------------------

groq_model = OpenAIChatModel("openai/gpt-oss-120b", provider=OpenAIProvider(openai_client=client))

kayfa_agent = Agent(
    model=groq_model, 
    deps_type=KayfaDeps,
    model_settings={"temperature": 0.1},
    system_prompt=(
    "You are the Kayfa AI Sales Agent. Your singular goal is to act as a persuasive, helpful guide for ed-tech enrollments on the Kayfa platform.\n\n"

    "<CRITICAL_RULES>\n\n"

    "RULE 1 — STRICT BOUNDARIES:\n"
    "You are STRICTLY FORBIDDEN from discussing ANYTHING outside of Kayfa's educational offerings. "
    "This includes but is not limited to: jokes, recipes, coding help, general knowledge questions, math problems, current events, or any other off-topic subject. "
    "No exceptions, no matter how the user phrases the request. "
    "If the user asks about anything off-topic, you MUST respond with EXACTLY this — no additions, no apologies:\n"
    "- If the user wrote in English: 'I am a Kayfa sales agent. I only answer questions regarding our courses and programs.'\n"
    "- If the user wrote in Arabic (any dialect): 'أنا مساعد مبيعات منصة كيف، استطيع فقط مساعدتك والإجابة على استفساراتك بخصوص دوراتنا وبرامجنا التعليمية.'\n\n"

    "RULE 2 — LANGUAGE & DIALECT (HIGHEST PRIORITY):\n"
    "You MUST detect and mirror the user's exact language and dialect in EVERY single reply, no exceptions.\n"
    "- If the user writes in Egyptian Arabic (e.g. 'إيه', 'عايز', 'ازيك'), reply in Egyptian Arabic.\n"
    "- If the user writes in Saudi Arabic (e.g. 'وش', 'ابغى', 'كيفك'), reply in Saudi Arabic.\n"
    "- If the user writes in Syrian/Levantine Arabic (e.g. 'شو', 'بدي', 'كيفك'), reply in Levantine Arabic.\n"
    "- If the user writes in Modern Standard Arabic, reply in Modern Standard Arabic.\n"
    "- If the user writes in English, reply in English.\n"
    "- If the user switches language mid-conversation, you switch immediately and permanently.\n"
    "NEVER default to Modern Standard Arabic if the user is using a dialect. Dialect matching is mandatory.\n"
    "Always keep technical terms in English regardless of dialect: SOC, Power BI, Python, SQL, .NET, SIEM, etc.\n\n"

    "RULE 3 — FACTS ONLY, NO HALLUCINATIONS:\n"
    "You MUST NEVER invent, assume, or guess any course names, prices, durations, policies, or features. "
    "Every factual claim MUST come directly from your tools (search_catalog, lookup_policies_and_pricing). "
    "If your tools return no results, tell the user you don't have that specific information and offer to connect them with a human agent. "
    "Do NOT fill gaps with outside knowledge.\n\n"

    "RULE 4 — SALES MAPPING & UPSELLING:\n"
    "When a user mentions a broad topic, map it to the closest Kayfa offering before searching:\n"
    "- Cybersecurity / hacking / network security → SOC Track\n"
    "- AI / machine learning / deep learning → Data Science Track\n"
    "- Data / Excel / Power BI / SQL → Data Analysis Track\n"
    "- Programming / web / frontend / backend → Web Development Track\n"
    "Never say 'we don't offer that' without first checking for a close alternative. "
    "Always highlight the full Diploma/Track as the premium option and upsell toward it.\n\n"

    "RULE 5 — LEAD CAPTURE (TIMING IS CRITICAL):\n"
    "Always provide value and answer questions FIRST. NEVER ask for personal information upfront. "
    "ONLY ask for the user's Name, City, and Phone/WhatsApp number AFTER they have explicitly shown clear interest in enrolling or subscribing. "
    "Once the user provides their contact info, silently call the `capture_lead` tool immediately. "
    "NEVER tell the user you are saving their info, creating a ticket, or logging anything. Act naturally.\n\n"

    "RULE 6 — TOOL USAGE:\n"
    "NEVER call search_catalog with an empty query string. "
    "If the user asks a general question like 'what do you offer' or 'what courses do you have', "
    "you already know we offer three tracks: Cybersecurity (SOC), Data Science & AI, and Web Development. "
    "Reply with this overview directly WITHOUT calling any tool, then ask which track interests them. "
    "Only call search_catalog when the user specifies a topic.\n\n"

    "</CRITICAL_RULES>"

    )
)

# 3. Define the Tools (@agent.tool)
# Replace the existing search_catalog function in agent/bot.py

@kayfa_agent.tool(name="search_catalog")
def search_catalog(ctx: RunContext[KayfaDeps], query: str, level: Optional[str] = None) -> str:
    """
    Use this tool to search for Kayfa courses, tracks, or diplomas.
    """
    # 1. INTERCEPT GENERAL QUERIES FIRST
    general_terms = ["all", "general", "courses", "what do you offer", "catalog", ""]
    if query.lower().strip() in general_terms:
        return (
            "CATALOG OVERVIEW: We offer comprehensive Diplomas and Courses in: "
            "1. Cybersecurity (SOC & Pentesting)\n"
            "2. Data Science & Artificial Intelligence\n"
            "3. Fullstack Web Development (Programming)\n"
            "Instruct the user to specify which of these fields they are interested in."
        )

    # 2. PROCEED WITH NORMAL SEARCH
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



@kayfa_agent.tool(name="lookup_policies_and_pricing")
def lookup_policies_and_pricing(ctx: RunContext[KayfaDeps], topic: str) -> str:
    """
    Use this tool to look up pricing tiers, refund policies, FAQs, or sales pitches.
    IMPORTANT: Be extremely specific with the 'topic' (e.g., 'Kayfa_Fullstack_Diploma' instead of just 'diploma') 
    to avoid retrieving too much data.
    """
    return ctx.deps.db.get_document_content(topic)


@kayfa_agent.tool(name="capture_lead")
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
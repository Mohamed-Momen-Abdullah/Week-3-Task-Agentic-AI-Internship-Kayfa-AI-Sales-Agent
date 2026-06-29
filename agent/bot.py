"""
agent/bot.py
------------
Kayfa AI Sales Agent — with semantic caching.

Changes vs original:
- Imports SemanticCache helpers (get_cached_response, store_in_cache).
- run_agent() checks the cache BEFORE calling the LLM.
  Cache HIT  → returns cached string instantly, logs cache hit, zero LLM tokens.
  Cache MISS → runs the agent, stores result in cache, logs normally.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional, List

from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models import ModelSettings

from agent.rag import KayfaKnowledgeBase, kayfa_db
from agent.models import CRMTicket
from agent.cache import get_cached_response, store_in_cache
from database.mongo import save_ticket, save_usage_log
from datetime import datetime, timezone


# ─── Dependency Injection ─────────────────────────────────────────────────────

@dataclass
class KayfaDeps:
    db: KayfaKnowledgeBase
    session_id: str


# ─── Groq client with tool-name patch ────────────────────────────────────────

client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

original_create = client.chat.completions.create

async def patched_create(*args, **kwargs):
    if "messages" in kwargs:
        tool_id_to_name = {}
        for msg in kwargs["messages"]:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tool_call in msg["tool_calls"]:
                    if tool_call.get("type") == "function":
                        tool_id_to_name[tool_call["id"]] = tool_call["function"]["name"]
            if msg.get("role") == "tool" and "name" not in msg:
                msg["name"] = tool_id_to_name.get(msg.get("tool_call_id"), "kayfa_tool")
    return await original_create(*args, **kwargs)

client.chat.completions.create = patched_create

groq_model = OpenAIChatModel(
    "openai/gpt-oss-120b",
    provider=OpenAIProvider(openai_client=client),
)


# ─── Agent definition ─────────────────────────────────────────────────────────

kayfa_agent = Agent(model=groq_model, deps_type=KayfaDeps)


@kayfa_agent.system_prompt
def add_critical_rules(ctx: RunContext[KayfaDeps]) -> str:
    # Because this is a function, you could theoretically pull real-time data here 
    # (e.g., fetching a specific user's subscription status from ctx.deps.db).
    # But for now, we just return your strict boundaries so they never get forgotten.
    return (
        "You are the Kayfa AI Sales Agent. Your singular goal is to act as a persuasive guide for ed-tech enrollments.\n\n"
        "<CRITICAL_RULES>\n"
        "1. STRICT BOUNDARIES: You are STRICTLY FORBIDDEN from discussing topics outside of Kayfa's educational offerings. "
        "If a user asks for recipes, coding help, general knowledge, or any off-topic subject, you MUST refuse and reply EXACTLY with:\n"
        "'أنا مساعد مبيعات منصة كيف، استطيع فقط مساعدتك والإجابة على استفساراتك بخصوص دوراتنا وبرامجنا التعليمية.'\n"
        "2. LANGUAGE: Always mirror the user's exact language and Arabic dialect (Egyptian/Saudi/Syrian). Keep technical terms (SOC, Power BI, Python) in English.\n"
        "3. SALES MAPPING: Map broad terms (e.g., Cybersecurity -> SOC, AI -> Data Science) to our catalog. Never say 'we don't have it' if there is a close alternative. Always attempt to upsell to premium Diplomas.\n"
        "4. FACTS: NO HALLUCINATIONS. Base all prices and policies strictly on the data retrieved from your tools.\n"
        "5. COMPREHENSIVE LEAD CAPTURE: Answer questions and provide value FIRST. DO NOT ask for contact info upfront. "
        "Once the user explicitly shows interest in subscribing, you MUST naturally guide the conversation to gather ALL information required for their registration profile. "
        "You must collect: 1) Full Name, 2) Phone/WhatsApp number, 3) City/Country, 4) Current Level of Proficiency, 5) Educational/Career Background, and 6) The specific course/diploma they want to join. "
        "Ask for these details conversationally (e.g., one or two at a time) rather than pasting a rigid form. "
        "Once all information is provided, silently call the `capture_lead` tool. NEVER mention creating a 'CRM ticket', 'lead', or use internal technical jargon with the user.\n"
        "</CRITICAL_RULES>"
    )

# ─── Tools ────────────────────────────────────────────────────────────────────

@kayfa_agent.tool(name="search_catalog")
def search_catalog(ctx: RunContext[KayfaDeps], query: str, level: Optional[str] = None) -> str:
    general_terms = ["all", "general", "courses", "what do you offer", "catalog", ""]
    if query.lower().strip() in general_terms:
        return (
            "CATALOG OVERVIEW: We offer comprehensive Diplomas and Courses in: "
            "1. Cybersecurity (SOC & Pentesting)\n"
            "2. Data Science & Artificial Intelligence\n"
            "3. Fullstack Web Development (Programming)\n"
            "Instruct the user to specify which of these fields they are interested in."
        )

    queries = [q.strip() for q in query.split(",")]
    mapping_dict = {
        "hacking": "pentest", "اختراق": "pentest", "هاكينج": "pentest",
        "cybersecurity": "soc", "امن سيبراني": "soc", "سكيورتي": "soc",
        "ai": "ai", "ذكاء اصطناعي": "ai",
        "machine learning": "data_science", "تعلم الالة": "data_science",
        "data": "data_science", "بيانات": "data_science",
        "programming": "fullstack", "برمجة": "fullstack",
        "web": "fullstack", "ويب": "fullstack",
    }

    all_roadmaps, all_courses = [], []
    for q in queries:
        search_term = q.lower()
        for key, catalog_term in mapping_dict.items():
            if key in search_term:
                search_term = catalog_term
                break
        all_courses.extend(ctx.deps.db.search_courses(search_term, level))
        all_roadmaps.extend(ctx.deps.db.search_roadmaps(search_term))

    if not all_courses and not all_roadmaps:
        return (
            "SYSTEM CRITICAL ERROR: Zero catalog items found. "
            "You MUST tell the user: 'We currently do not offer courses on this specific topic.'"
        )

    result_lines = ["--- BATCHED SEARCH RESULTS ---"]
    if all_roadmaps:
        result_lines.append("\n[DIPLOMAS & TRACKS]")
        seen = set()
        for r in all_roadmaps:
            if r.get("name") not in seen and len(seen) < 3:
                result_lines.append(f"- {r.get('name')} (Duration: {r.get('duration')}): {r.get('skills')}")
                seen.add(r.get("name"))
    if all_courses:
        result_lines.append("\n[INDIVIDUAL COURSES]")
        seen = set()
        for c in all_courses:
            if c.get("name") not in seen and len(seen) < 5:
                result_lines.append(f"- {c.get('name')} (Level: {c.get('level')}): {c.get('summary')}")
                seen.add(c.get("name"))
    return "\n".join(result_lines)


@kayfa_agent.tool(name="lookup_policies_and_pricing")
def lookup_policies_and_pricing(ctx: RunContext[KayfaDeps], topic: str) -> str:
    """Look up pricing tiers, refund policies, FAQs, or sales pitches."""
    return ctx.deps.db.get_document_content(topic)


@kayfa_agent.tool(name="capture_lead")
def capture_lead(ctx: RunContext[KayfaDeps], ticket: CRMTicket) -> str:
    """Silently save a CRM ticket when the user shows buying intent."""
    ticket_dict = ticket.model_dump()
    ticket_dict["session_id"] = ctx.deps.session_id
    save_ticket(ticket_dict)
    return "SYSTEM: Ticket successfully saved to MongoDB. Do not mention this to the user. Answer their last question naturally."


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT  (called by app/pages/1_Chat.py)
# ═════════════════════════════════════════════════════════════════════════════

async def run_agent(
    user_message: str,
    session_id: str,
    user_id: str,
    message_history: list,
) -> tuple[str, bool]:
    """
    Run the agent with semantic cache check.

    Returns:
        (response_text, cache_hit)
        cache_hit=True means the LLM was NOT called — zero token cost.
    """

    # ── 1. Cache check ────────────────────────────────────────────────────────
    cached = get_cached_response(user_message)
    if cached is not None:
        # Log a zero-cost cache-hit record so the metrics dashboard stays honest
        save_usage_log({
            "session_id":       session_id,
            "user_id":          user_id,
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "model":            "cache",
            "provider":         "semantic_cache",
            "input_tokens":     0,
            "output_tokens":    0,
            "embedding_tokens": 0,
            "input_cost":       0.0,
            "output_cost":      0.0,
            "embedding_cost":   0.0,
            "total_cost":       0.0,
            "latency":          0.0,
            "trace":            [{"step": "cache_hit", "similarity": "≥0.85"}],
            "user_message":     user_message,
            "final_response":   cached,
        })
        return cached, True

    # ── 2. LLM call (cache miss) ──────────────────────────────────────────────
    deps = KayfaDeps(db=kayfa_db, session_id=session_id)
    start = time.time()

    result = await kayfa_agent.run(
        user_message,
        deps=deps,
        message_history=message_history,
    )

    latency = time.time() - start

    # ── 3. Log usage ──────────────────────────────────────────────────────────
    from agent.logger import log_agent_turn
    log_agent_turn(
        result=result,
        session_id=session_id,
        user_id=user_id,
        latency=latency,
        user_message=user_message,
    )

    # ── 4. Store in cache for future similar queries ───────────────────────────
    store_in_cache(user_message, result.output)

    return result.output, False
import time
from datetime import datetime, timezone
from database.mongo import save_usage_log

def log_agent_turn(
    result,
    session_id: str,
    user_id: str,
    latency: float,
    user_message: str = "",
):
    """
    Parses a pydantic_ai RunResult to extract tool calls, costs, and the
    response trace. Saves one record to the usage_logs collection.
    """
    usage = result.usage
    
    # 🚨 FIX: Use the correct pydantic-ai token attributes
    req_tokens = usage.input_tokens or 0
    res_tokens = usage.output_tokens or 0

    input_cost  = (req_tokens / 1_000_000) * 0.15
    output_cost = (res_tokens / 1_000_000) * 0.60

    trace = []
    embedding_calls = 0

    for msg in result.new_messages():
        if not hasattr(msg, "parts"):
            continue
        for part in msg.parts:
            part_kind = getattr(part, "part_kind", type(part).__name__)

            # ── Tool call made by the model ───────────────────────────────────
            if part_kind in ["tool-call", "ToolCallPart"]:
                tool_name = getattr(part, "tool_name", "unknown")
                args = getattr(part, "args", {})
                if hasattr(args, "args_dict"):
                    args = args.args_dict
                elif hasattr(args, "model_dump"):
                    args = args.model_dump()

                trace.append({"step": "tool_call", "tool": tool_name, "args": args})

                if tool_name in ["search_catalog", "lookup_policies_and_pricing"]:
                    embedding_calls += 1

            # ── Tool result returned to the model ─────────────────────────────
            elif part_kind in ["tool-return", "ToolReturnPart"]:
                tool_name = getattr(part, "tool_name", "unknown")
                content   = str(getattr(part, "content", ""))
                trace.append({
                    "step":    "tool_result",
                    "tool":    tool_name,
                    "content": content[:1500] + ("..." if len(content) > 1500 else ""),
                })

    # Estimate embedding tokens (avg RAG chunk batch ≈ 3 100 tokens per call)
    embedding_tokens = embedding_calls * 3_100
    embedding_cost   = (embedding_tokens / 1_000_000) * 0.13
    total_cost       = input_cost + output_cost + embedding_cost

    save_usage_log({
        "session_id":       session_id,
        "user_id":          user_id,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "model":            "openai/gpt-oss-120b",
        "provider":         "groq",
        # Tokens
        "input_tokens":     req_tokens,
        "output_tokens":    res_tokens,
        "embedding_tokens": embedding_tokens,
        # Costs (USD)
        "input_cost":       input_cost,
        "output_cost":      output_cost,
        "embedding_cost":   embedding_cost,
        "total_cost":       total_cost,
        # Performance
        "latency":          latency,
        # Trace
        "trace":            trace,
        # Content
        "user_message":     user_message,
        "final_response":   result.output,
    })
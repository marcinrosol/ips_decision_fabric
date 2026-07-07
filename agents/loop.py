"""Manual agentic loop over a local Ollama model, using the MCP bridge for
tools. Ollama has no built-in tool-runner (unlike the Anthropic SDK) -- this
loop calls the model, executes any tool calls it requests via MCP, feeds
results back, and repeats until the model stops calling tools."""

import json

import ollama

from agents import mcp_bridge
from agents.config import get_model

MODEL = get_model()
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """You are the IPS Decision Fabric assistant, a decision-support \
agent for a pyrotechnics/energetics research lab. You have two tools for \
grounding your answers: search_corpus (the IPS proceedings, 1968-2022) for \
formulation guidance and technical background, and inventory/schedule tools \
for live stock and experiment state.

When asked a formulation question, call search_corpus first to ground your \
answer in the literature -- always cite what you find. Then cross-reference \
any chemicals involved against live inventory with get_chemical_status or \
list_low_stock_chemicals before recommending next steps.

When you reach an actionable recommendation (reorder a chemical, schedule an \
experiment, flag a compliance or storage-compatibility issue), call \
log_decision to record it, and draft_purchase_order / draft_experiment_schedule \
if the recommendation is concrete enough to draft. These only ever create \
Draft/Pending records for a human to review -- never claim something has been \
ordered or approved."""


async def answer(question: str, history: list[dict] | None = None) -> dict:
    """Runs the full tool-calling loop for one question, continuing from any
    prior turns in `history` (as returned by a previous call -- excludes the
    system prompt, which is always reconstructed fresh here). Returns
    {"response": str, "tool_calls": [{"name", "args", "result"}, ...],
    "history": [...]} -- pass "history" back into the next call for
    conversation continuity."""
    client = ollama.AsyncClient()
    tool_calls_made = []

    async with mcp_bridge.connect() as session:
        tools = await mcp_bridge.list_ollama_tools(session)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": question})

        for _ in range(MAX_TOOL_ROUNDS):
            response = await client.chat(model=MODEL, messages=messages, tools=tools)
            message = response["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return {
                    "response": message.get("content") or "",
                    "tool_calls": tool_calls_made,
                    "history": messages[1:],
                }

            for call in tool_calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                result = await mcp_bridge.call_tool(session, name, args)
                tool_calls_made.append({"name": name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result, default=str)})

        return {
            "response": "Reached the tool-call limit without a final answer -- try rephrasing.",
            "tool_calls": tool_calls_made,
            "history": messages[1:],
        }

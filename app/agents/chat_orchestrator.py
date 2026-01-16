"""Chat-orchestrator agent using OpenAI Agents SDK with Official MCP SDK transport.

Connects to the FastMCP server via MCPServerStreamableHttp, passing the user's
JWT in the Authorization header. The MCP server validates the token and scopes
all tool calls to the authenticated user.

Pattern reference: @.claude/skills/openai-agent-sdk-integration
Architecture: Agent → MCP HTTP Transport → FastMCP Server → CRUD operations
"""

import logging

from agents import Agent, Runner, RunConfig, OpenAIChatCompletionsModel
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)

# ============================================
# GEMINI CLIENT (REUSED ACROSS REQUESTS)
# ============================================

_gemini_client: AsyncOpenAI | None = None


def get_gemini_client() -> AsyncOpenAI:
    """Get or create Gemini client via OpenAI-compatible endpoint."""
    global _gemini_client

    if _gemini_client is None:
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        _gemini_client = AsyncOpenAI(
            api_key=settings.google_api_key.strip(),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        logger.info("Gemini client created")

    return _gemini_client


# ============================================
# LLM MODEL (OPENAI AGENTS SDK WRAPPER)
# ============================================

_llm_model: OpenAIChatCompletionsModel | None = None


def get_llm_model() -> OpenAIChatCompletionsModel:
    """Get Gemini model wrapped in OpenAI Agents SDK."""
    global _llm_model

    if _llm_model is None:
        client = get_gemini_client()
        _llm_model = OpenAIChatCompletionsModel(
            model=settings.chat_model,
            openai_client=client,
        )
        logger.info(f"LLM model created: {settings.chat_model}")

    return _llm_model


# ============================================
# RUN CONFIG (TRACING DISABLED)
# ============================================

_run_config: RunConfig | None = None


def get_run_config() -> RunConfig:
    """Get RunConfig with tracing disabled."""
    global _run_config

    if _run_config is None:
        _run_config = RunConfig(tracing_disabled=True)
        logger.info("Agent run config created (tracing disabled)")

    return _run_config


# ============================================
# SYSTEM PROMPT
# ============================================

SYSTEM_PROMPT = """You are a helpful task management assistant. Your role is to help users manage their tasks through natural conversation.

## Capabilities

You can help users with:
- **Creating tasks**: Add new tasks to their list
- **Listing tasks**: Show all their current tasks
- **Completing tasks**: Mark tasks as done
- **Updating tasks**: Change task title or description
- **Deleting tasks**: Remove tasks from their list

## Available Tools

You have access to MCP tools for task management:
- `add_task`: Create a new task with a title and optional description
- `list_tasks`: Get all of the user's tasks
- `complete_task`: Toggle a task's completion status
- `update_task`: Update a task's title, description, or completion status
- `delete_task`: Remove a task permanently
- `get_task_stats`: Get task statistics (total, completed, pending)
- `bulk_update_tasks`: Update multiple tasks at once

## Guidelines

1. **Be friendly and conversational**: Respond naturally and helpfully
2. **Confirm actions**: After completing an action, confirm what you did
3. **Handle ambiguity**: If a request is unclear, ask for clarification
4. **Match tasks by context**: Use task titles or IDs to identify tasks
5. **Multiple matches**: If multiple tasks match, list them and ask which one
6. **Off-topic requests**: Politely redirect to task management with examples
7. **Chain operations**: For multi-step requests, execute tools in sequence

## Examples of requests you can handle:
- "Add a task to buy groceries"
- "What's on my list?"
- "Show me my tasks"
- "Mark the groceries task as done"
- "I finished task 3"
- "Change 'buy milk' to 'buy almond milk'"
- "Delete task 5"
- "Remove the old task"
- "Create a meeting task and then show me all my tasks"
- "Add another one" (context-aware follow-up)
- "Complete task 3 and delete it" (multi-step)

## Response Format

When you perform actions:
- Confirm what was done in natural language
- Include relevant details (task title, ID if helpful)
- Offer helpful follow-up suggestions when appropriate

When listing tasks:
- Format as a readable list
- Show task status (pending/completed)
- Include task IDs when helpful for reference

## Handling Off-Topic Requests

For non-task-related messages, respond with:
"I'm here to help you manage your tasks! You can say things like:
- 'Add a task to call mom'
- 'Show my tasks'
- 'Mark groceries as done'
- 'Delete task 3'

What would you like to do with your tasks?"

## Error Handling

If something goes wrong:
- Explain the issue in simple terms
- Suggest what the user can try
- Never expose technical error details
"""


# ============================================
# AGENT RUNNER
# ============================================

async def run_agent(
    user_message: str,
    history: list[dict],
    authorization: str
) -> str:
    """Run the chat-orchestrator agent via Official MCP SDK HTTP transport.

    The agent connects to the MCP server with the user's JWT in the
    Authorization header. MCPAuthMiddleware on the server side validates
    the token and scopes all tool calls to the authenticated user.

    Args:
        user_message: The user's natural language message
        history: Prior conversation messages [{"role": "...", "content": "..."}]
        authorization: JWT Authorization header (e.g. "Bearer <token>")

    Returns:
        The agent's response message string

    Raises:
        Exception: If agent execution or MCP connection fails
    """
    try:
        # Configure MCP HTTP connection with JWT forwarded in Authorization header.
        # MCPAuthMiddleware on the server will validate this token and populate
        # the contextvars user context so MCP tools can scope to the correct user.
        mcp_params = MCPServerStreamableHttpParams(
            url=settings.mcp_server_url,
            headers={"Authorization": authorization},
        )

        async with MCPServerStreamableHttp(
            params=mcp_params,
            name="TaskMCPClient",
            cache_tools_list=True,  # Cache tool definitions for performance
        ) as mcp_server:
            # Agent discovers tools dynamically from the MCP server — no manual
            # @function_tool wrappers needed. All task mutations go through MCP.
            agent = Agent(
                name="chat-orchestrator",
                instructions=SYSTEM_PROMPT,
                mcp_servers=[mcp_server],
                model=get_llm_model(),
            )

            # Build conversation input from history + new user message
            input_messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history
            ]
            input_messages.append({"role": "user", "content": user_message})

            result = await Runner.run(
                starting_agent=agent,
                input=input_messages,
                run_config=get_run_config(),
            )

            return result.final_output

    except ConnectionError as e:
        logger.error(f"MCP server connection failed: {e}")
        raise RuntimeError(
            "I'm having trouble connecting to the task system right now. "
            "Please try again in a moment."
        ) from e
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        raise

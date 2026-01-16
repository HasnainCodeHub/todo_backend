# MCP Server for AI Task Management

This is an MCP (Model Context Protocol) Server that exposes task management capabilities as stateless tools for AI agents. The server implements five core tools that operate on user-scoped tasks stored in Neon PostgreSQL. The server enforces strict user isolation through JWT authentication and implements rate limiting while maintaining deterministic behavior with standardized error responses.

## Features

- **MCP Tools**: Implements five core tools for task management:
  - `add_task`: Create new tasks
  - `list_tasks`: Retrieve tasks by status
  - `complete_task`: Mark tasks as completed
  - `update_task`: Modify task details
  - `delete_task`: Remove tasks

- **Authentication**: JWT-based authentication with user isolation
- **Persistence**: SQLModel with Neon PostgreSQL for reliable storage
- **Rate Limiting**: Per-user rate limiting to prevent abuse
- **Error Handling**: Standardized error responses across all tools
- **Stateless Operation**: No in-memory caching, fully deterministic behavior

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   ```bash
   export DATABASE_URL="your_neon_postgres_url"
   export JWT_SECRET="your_jwt_secret"
   export JWT_ALGORITHM="HS256"
   ```

3. Initialize the database:
   ```bash
   python -m app.database init
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Environment Variables

- `DATABASE_URL`: Connection string for Neon PostgreSQL
- `JWT_SECRET`: Secret key for JWT validation
- `JWT_ALGORITHM`: Algorithm used for JWT signing (default: HS256)
- `RATE_LIMIT_REQUESTS`: Number of requests per user per minute (default: 100)
- `RATE_LIMIT_WINDOW`: Time window in seconds for rate limiting (default: 60)

## Architecture

The server follows a clean architecture with separated concerns:
- `models/`: SQLModel definitions for data persistence
- `schemas/`: Pydantic schemas for validation
- `tools/`: MCP tool definitions and registration
- `services/`: Business logic for task operations
- `dependencies/`: Authentication and authorization
- `utils/`: Helper functions like rate limiting
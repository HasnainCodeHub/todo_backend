# Claude Code Rules — Backend Layer

AI-Based Todo Application backend built with FastAPI and Python.

**Inherits from**: Root `CLAUDE.md` (project-wide rules apply)

**Live URL**: `https://todo-backend-xi-eosin.vercel.app`

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | 0.115.0 | High-performance REST API framework |
| **Python** | 3.13+ | Backend language |
| **SQLModel** | 0.0.22 | ORM with Pydantic validation |
| **PyJWT** | 2.10.1 | JWT token verification |
| **psycopg2-binary** | 2.9.10 | PostgreSQL driver |
| **Uvicorn** | 0.32.0 | ASGI server |
| **python-dotenv** | 1.0.0 | Environment configuration |

## Directory Structure (Actual)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   │                              # - CORS middleware
│   │                              # - Request logging
│   │                              # - Exception handlers
│   │                              # - Router registration
│   │
│   ├── config.py                  # Settings class with env vars
│   │                              # - DATABASE_URL
│   │                              # - JWT_SECRET
│   │                              # - JWT_ALGORITHM
│   │                              # - OPENAI_API_KEY (Phase 3)
│   │                              # - MCP_SERVER_URL (Phase 3)
│   │
│   ├── database.py                # SQLModel engine & session
│   │                              # - get_engine()
│   │                              # - get_session()
│   │                              # - init_db()
│   │
│   ├── models/                    # SQLModel ORM entities
│   │   ├── __init__.py
│   │   ├── task.py                # Task model with user_id
│   │   └── conversation.py        # Conversation & Message models (Phase 3)
│   │
│   ├── schemas/                   # Pydantic request/response
│   │   ├── __init__.py
│   │   ├── task.py                # TaskCreate, TaskUpdate, TaskResponse
│   │   └── chat.py                # ChatRequest, ChatResponse (Phase 3)
│   │
│   ├── routers/                   # API route handlers
│   │   ├── __init__.py
│   │   ├── tasks.py               # /api/tasks endpoints
│   │   └── chat.py                # /api/chat endpoints (Phase 3)
│   │
│   ├── crud/                      # Database operations
│   │   ├── __init__.py
│   │   ├── task.py                # CRUD functions with user scoping
│   │   └── conversation.py        # Conversation CRUD (Phase 3)
│   │
│   ├── services/                  # Business logic layer
│   │   ├── __init__.py
│   │   ├── task_service.py        # Task service
│   │   └── chat_service.py        # Chat orchestration (Phase 3)
│   │
│   ├── agents/                    # AI agent implementations (Phase 3)
│   │   ├── __init__.py
│   │   └── chat_orchestrator.py   # OpenAI Agents SDK agent
│   │
│   └── dependencies/              # FastAPI dependencies
│       ├── __init__.py
│       └── auth.py                # JWT verification (CRITICAL)
│
├── api/
│   └── index.py                   # Vercel serverless entry point
│
├── tests/
│   └── test_auth.py               # Authentication tests
│
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment template
```

## Boundary Rules

**This layer IS responsible for:**
- REST API endpoint implementation
- JWT token verification (NOT issuance)
- Business logic and validation
- Database operations via SQLModel
- User-scoped data access enforcement
- Error handling with proper HTTP status codes
- CORS configuration for frontend

**This layer MUST NOT:**
- Render HTML or UI components
- Issue JWT tokens (frontend Better Auth does this)
- Manage user sessions
- Expose database credentials in responses
- Allow cross-user data access
- Trust user_id from request body/headers

## Authentication Architecture

### JWT Verification Flow (DO NOT MODIFY)

```python
# dependencies/auth.py - JWT Verification
@dataclass
class AuthenticatedUser:
    """Extracted from JWT claims."""
    user_id: str
    email: str

async def get_current_user(
    authorization: Annotated[str | None, Header()] = None
) -> AuthenticatedUser:
    """
    1. Extract Bearer token from Authorization header
    2. Verify JWT signature with JWT_SECRET
    3. Validate expiration (PyJWT handles this)
    4. Extract user_id (sub) and email from claims
    5. Return AuthenticatedUser for downstream use
    """
    if not authorization:
        raise HTTPException(401, "Authentication required")

    # Parse "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Invalid authorization header format")

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return AuthenticatedUser(
            user_id=payload["sub"],
            email=payload["email"]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

### Protected Endpoint Pattern

```python
# routers/tasks.py
@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """User automatically extracted from JWT."""
    return crud.get_tasks(user_id=current_user.user_id)

@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    payload: TaskCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """user_id comes from JWT, NOT from request body."""
    return crud.create_task(
        title=payload.title,
        description=payload.description,
        user_id=current_user.user_id  # FROM JWT
    )
```

## API Endpoints

### Task Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/` | No | Service info |
| `GET` | `/health` | No | Health check |
| `GET` | `/api/ping` | No | CORS test |
| `GET` | `/api/tasks` | Yes | List user's tasks |
| `POST` | `/api/tasks` | Yes | Create task |
| `GET` | `/api/tasks/{id}` | Yes | Get specific task |
| `PUT` | `/api/tasks/{id}` | Yes | Update task |
| `DELETE` | `/api/tasks/{id}` | Yes | Delete task |
| `PATCH` | `/api/tasks/{id}/complete` | Yes | Toggle completion |

### Chat Endpoints (Phase 3: AI Chatbot Integration)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/chat` | Yes | Send message to AI assistant |
| `GET` | `/api/conversations` | Yes | List user's conversations |
| `GET` | `/api/conversations/{id}` | Yes | Get conversation with messages |
| `DELETE` | `/api/conversations/{id}` | Yes | Delete a conversation |

### Chat Request/Response Format

```python
# POST /api/chat request
{
    "message": "Add a task to buy groceries",
    "conversation_id": null  # or existing conversation UUID
}

# POST /api/chat response
{
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Done! I've added 'Buy groceries' to your task list.",
    "actions_taken": ["add_task: Buy groceries"],
    "created_at": "2026-02-06T10:30:00Z"
}
```

### Error Response Format

```python
# Consistent error structure
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human readable message"
    }
}

# Status codes
401 - Authentication required / Invalid token
403 - Access denied (task belongs to another user)
404 - Task not found
503 - Database error
500 - Internal server error
```

## Database Patterns

### SQLModel Entity

```python
# models/task.py
class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    description: str | None = None
    completed: bool = Field(default=False)
    user_id: str = Field(index=True)  # From JWT, NOT foreign key
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pydantic Schemas

```python
# schemas/task.py
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None

class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### CRUD Operations (User-Scoped)

```python
# crud/task.py
def get_tasks(user_id: str) -> list[Task]:
    """Always filter by user_id."""
    with get_session() as session:
        return session.exec(
            select(Task).where(Task.user_id == user_id)
        ).all()

def get_task(task_id: int, user_id: str) -> Task | None:
    """Verify ownership before returning."""
    with get_session() as session:
        return session.exec(
            select(Task)
            .where(Task.id == task_id)
            .where(Task.user_id == user_id)
        ).first()

def task_exists_any_user(task_id: int) -> bool:
    """Check if task exists (for 403 vs 404 decision)."""
    with get_session() as session:
        task = session.get(Task, task_id)
        return task is not None
```

## CORS Configuration

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",              # Dev
        "http://127.0.0.1:3000",              # Dev alt
        "https://ai-based-todo.vercel.app",   # Production
        "https://*.vercel.app",               # Preview deploys
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

## Coding Conventions

### Type Hints (Required)

```python
# All functions must have type hints
async def create_task(
    title: str,
    description: str | None,
    user_id: str
) -> Task:
    """Docstrings for public functions."""
    pass

# Use modern union syntax
def get_task(task_id: int, user_id: str) -> Task | None:
    pass
```

### Dependency Injection

```python
# Use Depends() for reusable dependencies
@router.get("/tasks")
async def list_tasks(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    pass
```

### Error Handling

```python
# Raise HTTPException with proper codes
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)

# Re-raise HTTPException in try/except
try:
    task = crud.get_task(task_id, user_id)
    if not task:
        raise HTTPException(404, "Task not found")
except HTTPException:
    raise  # Don't catch HTTPException
except Exception as e:
    raise HTTPException(503, f"Database error: {e}")
```

### File Naming

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case.py | `task_model.py` |
| Classes | PascalCase | `AuthenticatedUser` |
| Functions | snake_case | `get_current_user` |
| Constants | UPPER_SNAKE | `JWT_ALGORITHM` |

## Key Commands

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run with host binding
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=app
```

## Environment Variables

```bash
# .env (required)
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
JWT_SECRET=<shared-secret-with-frontend>
JWT_ALGORITHM=HS256

# Optional
LOG_LEVEL=INFO
```

## Important Notes

### DO NOT Modify

1. **JWT Verification** (`dependencies/auth.py`)
   - Signature verification logic
   - Claim extraction (sub, email)
   - Error response format

2. **User Scoping in CRUD** (`crud/task.py`)
   - All queries MUST include user_id filter
   - Never trust user_id from request body

3. **CORS Origins** (`main.py`)
   - Frontend URLs must be whitelisted
   - Don't use `allow_origins=["*"]` in production

4. **Error Response Structure**
   - `{"error": {"code": "...", "message": "..."}}`
   - Frontend depends on this format

### Security Rules

```python
# CORRECT: user_id from JWT
@router.post("/tasks")
async def create(
    payload: TaskCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    return crud.create_task(user_id=current_user.user_id, ...)

# WRONG: user_id from request body
@router.post("/tasks")
async def create(payload: TaskCreateWithUserId):  # NO!
    return crud.create_task(user_id=payload.user_id, ...)
```

### 403 vs 404 Pattern

```python
# Check if task exists for any user to return correct status
task = crud.get_task(task_id, user_id)
if not task:
    if crud.task_exists_any_user(task_id):
        raise HTTPException(403, "Access denied: task belongs to another user")
    raise HTTPException(404, "Task not found")
```

### Vercel Deployment

```python
# api/index.py - Serverless entry point
from app.main import app

# Vercel expects 'app' to be the ASGI application
```

```json
// vercel.json
{
  "builds": [
    { "src": "api/index.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "api/index.py" }
  ]
}
```

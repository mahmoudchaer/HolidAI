# HolidAI Database Setup Guide

This guide will help you set up the PostgreSQL database for user authentication.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+ installed
- pip package manager

## Step 1: Start PostgreSQL Database

Start the Dockerized PostgreSQL database:

```bash
docker-compose up -d
```

This will:
- Start PostgreSQL 16 in a Docker container
- Create the database `myproject` with user `admin` and password `admin123`
- Automatically create the `users` table on first startup
- Expose the database on port `5433` (to avoid conflicts with existing PostgreSQL)
- Create a persistent volume for data storage

To verify the database is running:

```bash
docker ps
```

You should see a container named `holidai_postgres` running.

## Step 2: Install Dependencies

Install the required Python packages:

```bash
pip install -r mcp_system/requirements.txt
pip install -r langraph/requirements.txt
pip install -r frontend/requirements.txt
```

The frontend requirements include:
- Flask (web framework)
- SQLAlchemy (database ORM)
- psycopg2-binary (PostgreSQL adapter)
- bcrypt (password hashing)
- python-dotenv (environment variables)

## Step 3: Start the Application

The authentication is integrated into the Flask frontend. Start the application:

**Terminal 1 - MCP Server:**
```bash
cd mcp_system/server
python main_server.py
```

**Terminal 2 - Flask Frontend (includes authentication):**
```bash
cd frontend
python app.py
```

The application will be available at `http://localhost:5000`

## Testing the Setup

### Test Signup

1. Open `http://localhost:5000/signup` in your browser
2. Enter an email and password (minimum 8 characters)
3. Click "Sign Up"
4. You should be redirected to the main page

### Test Login

1. Open `http://localhost:5000/login` in your browser
2. Enter your email and password
3. Click "Log In"
4. You should be redirected to the main page with your email displayed

## Database Management

### Connect to Database

You can connect to the PostgreSQL database using:

```bash
docker exec -it holidai_postgres psql -U admin -d myproject
```

### View Users Table

```sql
SELECT email, created_at, last_login FROM users;
```

### Stop Database

```bash
docker-compose stop postgres
```

### Start Database

```bash
docker-compose start postgres
```

### Restart Database

```bash
docker-compose restart postgres
```

### Remove Container (keeps data)

```bash
docker-compose down
```

### Remove Container and Data (⚠️ deletes all data)

```bash
docker-compose down -v
```

## Data Persistence

The database uses a Docker volume (`postgres_data`) to persist data. This means:
- ✅ Data persists when you stop the container
- ✅ Data persists when you restart the container
- ✅ Data persists when you remove the container (unless you use `-v` flag)
- ⚠️ Data is deleted only if you run `docker-compose down -v`

## Troubleshooting

### Database Connection Issues

- Ensure Docker is running
- Check if the container is running: `docker ps`
- Check container logs: `docker logs holidai_postgres`
- Verify port 5433 is not already in use
- If you see "password authentication failed", the database might need to be restarted

### Port Conflicts

If port 5433 is already in use, you can change it in `docker-compose.yml`:
```yaml
ports:
  - "5434:5432"  # Change 5433 to any available port
```

Then update `frontend/app.py` to use the new port:
```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin123@127.0.0.1:5434/myproject"  # Update port here
)
```

### Test Database Connection

Test if you can connect to the database:

```bash
python -c "import psycopg2; conn = psycopg2.connect('postgresql://admin:admin123@127.0.0.1:5433/myproject'); print('Connection successful!'); conn.close()"
```

## Next Steps

- Add JWT token authentication for enhanced security
- Implement password reset functionality
- Add user profile management
- Add email verification

# Scrub-a-Dub Hub Backend

A Flask-based REST API for viewing and managing office duties (cleaning the fridge and coffee machine) with tracking and completion status.

## API Endpoints

### GET /api/duties
Get all duties with optional limit parameter
- **Query Parameters**: `limit` (int, default: 100)
- **Response**: List of duty assignments with completion status

### POST /api/duties/complete
Mark a duty as completed
- **Body**: `{"duty_id": "123", "duty_type": "coffee"}`
- **Returns**: Updated duties list

### POST /api/duties/uncomplete
Mark a duty as uncompleted
- **Body**: `{"duty_id": "123", "duty_type": "fridge"}`
- **Returns**: Updated duties list

### GET /api/members
Get all office members
- **Response**: List of office members

### POST /api/members
Add a new office members
- **Response**: Updated list of office members

### DELETE /api/members
Deactivate an office member
- **Response**: Updated list of (active) office members

### PUT /api/members
Update an office member
- **Response**: Update list of office members

## Project Structure

```
├── app.py                  # Flask application and API endpoints
├── database.py             # Database models and operations
├── models.py               # Pydantic models for data validation
├── google_utils.py         # Google Secret Manager utilities
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container configuration
├── .pre-commit-config.yaml # Pre-commit hooks configuration
└── .venv/                  # Virtual environment
```

## Database Schema

### Members Table
- `id` (Primary Key)
- `username` (Unique)
- `full_name`
- `coffee_drinker` (Boolean)
- `active` (Boolean)

### Duty Assignments Table
- `id` (Primary Key)
- `member_id` (Foreign Key to members)
- `duty_type` ('coffee' or 'fridge')
- `assigned_at` (Timestamp)
- `cycle_id` (Integer)
- `completed` (Boolean)
- `completed_at` (Timestamp, nullable)


## Local Development

### Prerequisites
- Python 3.12+
- PostgreSQL database (or access to Neon/other hosted database)
- **For local development**: Database connection string
- **For production**: Google Cloud credentials (for Secret Manager access)

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd scrub-a-dub-hub-backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install pre-commit hooks** (optional, for development)
   ```bash
   pre-commit install
   ```

5. **Configure database connection**

   **Option A: Environment Variable (Recommended for local development)**
   ```bash
   export DATABASE_URL_DEV="postgresql://username:password@host:port/test_database"
   ```

   **Option B: Google Secret Manager (For access to the production database)**
   - Install Google Cloud CLI
   - Run `gcloud auth application-default login`
   - Ensure your account has access to the project
   - Secret expected:
     - `neon-database-connection-string` (connection string for production database)

### Running Locally

1. **Start the development server**
   ```bash
   python app.py
   ```

2. **Or use Flask's development server**
   ```bash
   export FLASK_APP=app.py
   export FLASK_ENV=development
   flask run
   ```

The API will be available at `http://localhost:4999`

### Development Tools

- **Code Formatting**: `ruff format`
- **Type Checking**: `mypy database.py --ignore-missing-imports --no-strict-optional`
- **Pre-commit**: Runs `ruff format` and `mypy` automatically on commit

## Deployment

### Google Cloud Run with Automatic Deployment

#### Initial Setup (One-time)

1. **Connect your GitHub repository to Cloud Run**

   In the Google Cloud Console:
   - Go to Cloud Run → Create Service
   - Select "Continuously deploy from a repository"
   - Connect your GitHub account and select this repository
   - Choose branch: `main` (or your preferred branch)
   - Build Type: Dockerfile
   - Dockerfile path: `/Dockerfile`

2. **Configure service settings**
   - CPU allocation: CPU is only allocated during request processing
   - Memory: 512 MiB
   - Maximum requests per container: 80
   - Container port: 8080
   - Container command and arguments: leave blank

3. **Set up authentication**
   Allow unauthenticated invocations (for public API)

4. **Configure environment variables**
   None needed.

5. **Set up Google Secret Manager**
   Create the required secrets in Google Secret Manager

6. **Grant Secret Manager access to Cloud Run**
    Give the service account access to the role 'roles/secretmanager.secretAccessor'

#### Automatic Deployment

Once set up, **every push to your main branch will automatically**:
1. Trigger a new build in Cloud Build
2. Create a new container image
3. Deploy the new image to Cloud Run
4. Route traffic to the new revision

### Required Google Cloud Services

Enable these services in your Google Cloud project:
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

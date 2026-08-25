# Moodometer

A web-based mood tracking application that uses a two-dimensional emotional grid to help users monitor and understand their emotional states over time.

## Overview

Moodometer is built on the **circumplex model of affect**, which represents emotions across two fundamental dimensions:
- **Energy Level**: High energy ↔ Low energy (vertical axis)
- **Valence**: Pleasant ↔ Unpleasant (horizontal axis)

This creates four main emotional quadrants with distinct mood zones, allowing users to track their emotional journey with nuance and precision.

## Features

- **Interactive Mood Board**: Visual 2D grid with 6 distinct mood zones
- **User Management**: Multi-user support with individual mood tracking
- **Mood History**: Track moods over time with timestamps
- **Journal Entries**: Add text entries alongside mood data
- **RESTful API**: FastAPI backend for easy integration
- **Database Integration**: PostgreSQL for persistent data storage
- **Containerized Deployment**: Docker and Docker Compose for easy setup
- **CI/CD Pipeline**: GitLab CI with security scanning

## Architecture

```
moodometer/
├── backend/
│   ├── app/
│   │   ├── app.py              # FastAPI application and endpoints
│   │   ├── User.py             # User model with mood/entry management
│   │   ├── index.html          # Frontend mood board interface
│   │   ├── requirements.txt    # Python dependencies
│   │   ├── .env                # Environment variables (not in repo)
│   │   └── static/
│   │       └── style.css       # Mood board styling
│   ├── db.py                   # Database connection utility
│   ├── Dockerfile              # Container image definition
│   └── docker-compose.yml      # Multi-container orchestration
├── .gitlab-ci.yml              # CI/CD pipeline configuration
└── README.md                   # This file
```

### Technology Stack

- **Backend**: Python 3.13, FastAPI, Uvicorn
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, Bootstrap 3
- **Deployment**: Docker, Docker Compose
- **CI/CD**: GitLab CI with SAST and Secret Detection

## Mood Board Zones

The interactive mood board features six emotional states organized by energy and valence:

### High Energy + Pleasant (Top Right)
- **"We are so fucking back"** - Optimistic recovery
  - **"Let's fucking goooo"** - Peak excitement and motivation

### High Energy + Unpleasant (Top Left)
- **"Fuck it we ball"** - Determined despite adversity

### Low Energy + Pleasant (Bottom Right)
- **"We vibing"** - Calm contentment

### Low Energy + Unpleasant (Bottom Left)
- **"It is what it is"** - Acceptance of difficult circumstances
  - **"It's so over"** - Deeper pessimism
    - **"Mom would be sad"** - Lowest emotional state

## Installation

### Prerequisites

- Docker and Docker Compose
- Git

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://gitlab.com/Percevase/moodwatch.git
   cd moodwatch
   ```

2. **Set up environment variables**
   ```bash
   cd backend/app
   cp .env.example .env  # Create from example if available
   # Edit .env with your database credentials
   ```

   Required environment variables:
   ```
   DATABASE_URL=postgresql://user:password@db:5432/moodometer
   ```

3. **Build and run with Docker Compose**
   ```bash
   cd backend
   docker-compose up --build
   ```

4. **Access the application**
   - Open your browser to `http://localhost:8000`
   - The API documentation is available at `http://localhost:8000/docs`

### Local Development Setup

1. **Install Python dependencies**
   ```bash
   cd backend/app
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set up PostgreSQL**
   - Install PostgreSQL locally or use a cloud instance
   - Create a database named `moodometer`
   - Update the `DATABASE_URL` in `.env`

3. **Run the application**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Test database connection**
   ```bash
   cd backend
   python db.py
   ```

## API Documentation

### Endpoints

#### `GET /`
Returns the main mood board interface (HTML page).

**Response**: HTML page with interactive mood board

#### `GET /users/{username}`
Retrieve user information by username.

**Parameters**:
- `username` (path): The username to look up

**Response**:
```json
"User(name=Percevase,password=Percevase)"
```

**Error Responses**:
- `404 Not Found`: User does not exist

### Current Test Users

The application initializes with six test users:
- Percevase
- Lanceloutre
- Karabouc
- Arthortur
- Tristambour
- Leodaglan

## User Model

The `User` class manages individual user data:

### Attributes
- `name`: Username (string)
- `password`: User password (string)
- `moods`: Dictionary mapping timestamps to mood tuples `(energy, valence)`
- `entries`: Dictionary mapping timestamps to journal entry strings

### Methods

**Mood Management**:
- `get_moods()`: Retrieve all mood entries
- `add_mood(timestamp, mood)`: Add a new mood entry
- `modify_mood(timestamp, mood)`: Update an existing mood entry
- `remove_mood(timestamp)`: Delete a mood entry

**Journal Entry Management**:
- `get_entries()`: Retrieve all journal entries
- `add_entry(timestamp, entry)`: Add a new journal entry
- `modify_entry(timestamp, entry)`: Update an existing entry
- `remove_entry(timestamp)`: Delete an entry

## Development

### Running Tests

```bash
# Tests will be added in future development
pytest
```

### Code Quality

The project uses GitLab CI for automated security scanning:
- **SAST (Static Application Security Testing)**: Analyzes code for vulnerabilities
- **Secret Detection**: Prevents accidental credential commits

### Project Structure

- **Backend Logic**: `backend/app/app.py` - FastAPI routes and application setup
- **Data Models**: `backend/app/User.py` - User class with mood tracking
- **Database**: `backend/db.py` - Database connection and testing
- **Frontend**: `backend/app/index.html` - Interactive mood board UI
- **Styling**: `backend/app/static/style.css` - Visual design and layout

## Deployment

### Docker Deployment

The application uses a multi-container setup:
- **Web Service**: FastAPI application (port 8000)
- **Database Service**: PostgreSQL with health checks

The `docker-compose.yml` ensures the web service waits for the database to be healthy before starting.

### Environment Configuration

Create a `.env` file in `backend/app/` with:
```env
DATABASE_URL=postgresql://username:password@db:5432/dbname
POSTGRES_USER=username
POSTGRES_PASSWORD=password
POSTGRES_DB=dbname
```

## Roadmap

- [ ] Implement full CRUD API endpoints for moods and entries
- [ ] Add user authentication and authorization
- [ ] Create data visualization for mood trends over time
- [ ] Implement mood analytics and insights
- [ ] Add export functionality (CSV, JSON)
- [ ] Mobile-responsive design improvements
- [ ] Real-time mood updates with WebSockets
- [ ] Integration with calendar applications

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Merge Request

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Write descriptive commit messages
- Add comments for complex logic

## License

This project is currently unlicensed. Please contact the project maintainers for usage permissions.

## Authors

- **Percevase** - Initial development

## Acknowledgments

- Inspired by the circumplex model of affect (Russell, 1980)
- Mood zone phrases inspired by internet culture and memes
- Built with FastAPI, PostgreSQL, and Docker

## Support

For issues, questions, or suggestions:
- Open an issue on GitLab
- Contact the development team

## Project Status

**Active Development** - The project is under active development. Core features are functional, with database integration and additional API endpoints in progress.

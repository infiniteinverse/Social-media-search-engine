# Tweet Search Engine

**A Python, PostgreSQL and Flask-based application for collecting, storing, and searching topic-specific tweets.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-lightgrey)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791)
![Status](https://img.shields.io/badge/Project-Academic%20Assignment-orange)

## Overview

Tweet Search Engine is a database-driven web application developed as part of the Programming Assignment: *Twitter(X) → Postgres → Web Query (Python)*.

The project demonstrates a complete data-processing workflow in which topic-related tweet records are collected, processed, stored in a normalized PostgreSQL database, and retrieved through a Flask-based web interface.

The application is designed to support topic-oriented tweet ingestion and structured searching using multiple attributes, including tweet content, hashtags, usernames, and dates.

The ingestion pipeline supports a mock-data mode using JSON payloads, allowing the database and application workflow to be tested independently of external API availability.

## Objectives

- Understand the integration of Python applications with PostgreSQL.
- Implement structured data ingestion and processing.
- Design a normalized relational database for social media data.
- Extract and manage tweet, user, and hashtag information.
- Maintain topic-to-tweet relationships.
- Develop a Flask web application for querying stored records.
- Implement safe, parameterized SQL queries.
- Provide a reproducible workflow for testing and demonstration.

## System Architecture

The application follows a modular architecture with separate components for data ingestion, database management, and web-based querying.

```mermaid
flowchart TD
    A["X API v2 / Mock JSON Payload"] --> B["Python Ingestion Pipeline"]
    B --> C["Data Extraction and Processing"]
    C --> D["PostgreSQL Database"]
    D --> E["Flask Web Application"]
    E --> F["Search Form"]
    F --> G["Parameterized SQL Queries"]
    G --> D
    D --> H["Filtered Tweet Results"]
    H --> I["HTML Results Table"]
```

### Workflow

1. A topic or search query is provided to the ingestion script.
2. The ingestion module obtains tweet data from the configured source.
3. User information, tweet attributes, engagement metrics, and hashtags are extracted.
4. Records are inserted or updated in PostgreSQL.
5. Topic-to-tweet relationships are recorded.
6. The Flask application accepts search parameters from the user.
7. SQL queries retrieve matching records from the database.
8. Results are displayed dynamically on the web interface.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.10+ |
| Web framework | Flask |
| Database | PostgreSQL |
| Database connectivity | psycopg2 |
| API communication | Requests / X API v2 |
| Configuration management | python-dotenv |
| Frontend | HTML, CSS, Jinja2 |
| Data format | JSON |
| Version control | Git and GitHub |

## Project Structure

```text
tweet-search-engine/
│
├── db/
│   ├── create_schema.sql
│   └── ...
│
├── ingest/
│   ├── fetch_and_load.py
│   ├── sample_payload.json
│   └── mock_assignment_payload.json
│
├── web/
│   ├── app.py
│   ├── templates/
│   │   ├── base.html
│   │   └── index.html
│   └── static/
│       └── styles.css
│
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── REPORT.md
```

*The structure above represents the intended project organization. Retain only files and folders that actually exist in your repository.*

## Database Design

The database follows a normalized relational structure consisting of five tables.

### 1. Users

Stores information about the authors of tweets.

| Attribute | Description |
|---|---|
| user_id | Unique user identifier (Primary Key) |
| username | Account username |
| display_name | User's display name |
| created_at | Account creation timestamp |
| followers_count | Number of followers |
| verified | Verification status |

### 2. Tweets

Stores the actual tweet records and engagement information.

| Attribute | Description |
|---|---|
| tweet_id | Unique tweet identifier (Primary Key) |
| user_id | Author identifier (Foreign Key) |
| text | Tweet content |
| created_at | Tweet creation timestamp |
| lang | Language code |
| like_count | Number of likes |
| retweet_count | Number of reposts |
| reply_count | Number of replies |
| quote_count | Number of quotes |

### 3. Hashtags

Stores hashtags independently from tweet records.

| Attribute | Description |
|---|---|
| tweet_id | Associated tweet (Foreign Key) |
| tag | Hashtag text |

The composite primary key `(tweet_id, tag)` prevents duplicate hashtag associations.

### 4. Topics

Maintains the search queries used during ingestion.

| Attribute | Description |
|---|---|
| topic_id | Unique topic identifier (Primary Key) |
| query | Search query |
| run_at | Ingestion execution timestamp |

### 5. Tweet_Topics

Maintains the many-to-many relationship between topics and tweets.

| Attribute | Description |
|---|---|
| topic_id | Topic identifier (Foreign Key) |
| tweet_id | Tweet identifier (Foreign Key) |

This structure allows one tweet to be associated with multiple search topics.

### Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ TWEETS : authors
    TWEETS ||--o{ HASHTAGS : contains
    TOPICS ||--o{ TWEET_TOPICS : produces
    TWEETS ||--o{ TWEET_TOPICS : belongs_to

    USERS {
        TEXT user_id PK
        TEXT username
        TEXT display_name
        TIMESTAMPTZ created_at
        INT followers_count
        BOOLEAN verified
    }

    TWEETS {
        TEXT tweet_id PK
        TEXT user_id FK
        TEXT text
        TIMESTAMPTZ created_at
        TEXT lang
        INT like_count
        INT retweet_count
        INT reply_count
        INT quote_count
    }

    HASHTAGS {
        TEXT tweet_id PK,FK
        TEXT tag PK
    }

    TOPICS {
        SERIAL topic_id PK
        TEXT query
        TIMESTAMPTZ run_at
    }

    TWEET_TOPICS {
        INT topic_id PK,FK
        TEXT tweet_id PK,FK
    }
```

## Installation and Setup

### Prerequisites

Install the following before running the application:

- Python 3.10 or later
- PostgreSQL 13 or later
- Git
- Visual Studio Code (recommended)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/tweet-search-engine.git

cd tweet-search-engine
```

### 2. Create a virtual environment

For Windows CMD:

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```cmd
python -m pip install --upgrade pip

pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root.

You can copy the example configuration:

```cmd
copy .env.example .env
```

Configure the following variables:

```env
X_BEARER_TOKEN=YOUR_X_BEARER_TOKEN

DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/tweetsdb

FLASK_DEBUG=1
PORT=5000
```

Replace the placeholders with your actual configuration.

**Security:** Never commit `.env` or expose API credentials in screenshots, source code, or public repositories.

### 5. Create the PostgreSQL database

```cmd
createdb -U postgres tweetsdb
```

### 6. Create the database schema

```cmd
psql -U postgres -d tweetsdb -f db/create_schema.sql
```

This creates the five relational tables required by the application.

## Data Ingestion

The project provides a Python ingestion module:

```text
ingest/fetch_and_load.py
```

It supports two execution modes.

### A. Mock ingestion mode

Mock mode reads a locally stored JSON payload and processes its contents without requiring a successful external API request.

Run:

```cmd
python ingest/fetch_and_load.py --query "generative ai" --from-file ingest/sample_payload.json
```

For the smaller assignment-specific test payload:

```cmd
python ingest/fetch_and_load.py --query "generative ai" --from-file ingest/mock_assignment_payload.json
```

The sample payload follows the general structure of an X API v2 search response, including tweet data, public metrics, hashtags, and expanded user information.

Mock mode is useful for:

- Testing database connectivity.
- Validating JSON parsing.
- Testing insertion and update operations.
- Verifying relational mappings.
- Demonstrating the application without consuming API credits.

### B. Live X API mode

The ingestion script also supports live API execution using a Bearer Token.

Example:

```cmd
python ingest/fetch_and_load.py --query "generative ai" --max 10
```

This mode requires:

- A valid X Developer account.
- A configured Bearer Token.
- Sufficient API credits and access to the required endpoint.

API availability and usage costs depend on the developer account and applicable X API plan.

**Current implementation status:** Mock ingestion has been tested successfully. Live API execution has reached the X API but returned HTTP 402 (`credits_depleted`) because the account did not have sufficient credits. Successful live tweet ingestion is therefore not claimed.

## Database Verification

Connect to the database:

```cmd
psql -U postgres -d tweetsdb
```

List all tables:

```sql
\dt
```

Check stored records:

```sql
SELECT COUNT(*) FROM users;

SELECT COUNT(*) FROM tweets;

SELECT COUNT(*) FROM hashtags;

SELECT COUNT(*) FROM topics;

SELECT COUNT(*) FROM tweet_topics;
```

View recent tweets:

```sql
SELECT
    t.tweet_id,
    u.username,
    t.text,
    t.like_count,
    t.retweet_count
FROM tweets t
JOIN users u
ON t.user_id = u.user_id
ORDER BY t.created_at DESC;
```

Exit:

```sql
\q
```

## Running the Web Application

The Flask application is located at:

```text
web/app.py
```

From the project root, activate the virtual environment and execute:

```cmd
venv\Scripts\activate

python web/app.py
```

The application is configured to run on port `5000`.

Open the following address in a browser:

```text
http://localhost:5000
```

The web application is designed to provide a search interface for retrieving stored tweets.

### Supported Search Parameters

| Parameter | Description |
|---|---|
| Text contains | Search tweet content |
| Hashtag | Filter by hashtag |
| Username | Filter by tweet author |
| Start date | Set the beginning of a date range |
| End date | Set the end of a date range |

### Results Display

The assignment specifies displaying the following information:

- Tweet creation timestamp.
- Username.
- Tweet content.
- Associated hashtags.
- Like count.
- Repost count.

The application uses PostgreSQL queries to retrieve matching records and renders the results using Jinja2 templates.

## SQL Query Safety

The web application should use parameterized SQL queries rather than inserting user input directly into SQL statements.

For example:

```python
sql = """
SELECT tweet_id, text
FROM tweets
WHERE text ILIKE %s
"""

params = [f"%{query}%"]

cur.execute(sql, params)
```

This helps prevent SQL injection and separates query structure from user-provided values.

## Testing and Validation

The following checks form the project's validation workflow:

| Test | Expected result |
|---|---|
| PostgreSQL connection | Successful connection |
| Schema creation | Five tables created |
| Mock JSON ingestion | Records inserted |
| User mapping | Correct user-to-tweet relationships |
| Hashtag extraction | Hashtag associations stored |
| Topic mapping | Topic-to-tweet relationships stored |
| Text search | Matching tweets returned |
| Hashtag search | Matching hashtag records returned |
| Username search | Tweets filtered by author |
| Date filtering | Results restricted to date range |

## Limitations

- Live X API ingestion depends on the account's API access and available credits.
- Mock payloads contain demonstration records and should not be interpreted as actual X posts.
- API rate limits may restrict the volume and frequency of live ingestion.
- Data accuracy in mock mode depends on the supplied JSON payload.
- Search results are limited to records already present in the PostgreSQL database.

## Future Improvements

Potential extensions include:

- Screenshot-based OCR ingestion for authorized, visible feed content.
- Improved duplicate detection and data validation.
- Pagination for larger result sets.
- Advanced search and sorting.
- Search by language.
- Data visualization for tweet engagement.
- Topic-wise analytics and trend analysis.
- Exporting filtered search results to CSV.
- Improved error handling and API retry mechanisms.

## Academic Context

**Course:** Product Innovation Laboratory  
**Assignment:** Programming Assignment 4  
**Project:** Twitter(X) → Postgres → Web Query (Python)

This project demonstrates the integration of data ingestion, relational database design, backend development, and dynamic web-based querying.

## Author

**Name:** YOUR NAME  
**Roll Number:** YOUR ROLL NUMBER  
**Institute:** National Institute of Technology Rourkela

---

*Developed for academic learning and experimentation.*
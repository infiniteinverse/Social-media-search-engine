# Development Log – Tweet Search Engine

**Project:** Tweet Search Engine
**Course:** Product Innovation Laboratory
**Assignment:** Assignment 4 – Twitter(X) → Postgres → Web Query (Python)

---

## Day 1 – Project Understanding and Requirement Analysis

**Objective:** Understand the assignment requirements and establish the overall application architecture.

**Work Performed:**

- Studied the assignment specification and identified the major functional requirements.
- Analysed the workflow involving tweet collection, database storage, and web-based querying.
- Identified Python as the primary programming language, PostgreSQL as the database, and Flask as the web framework.
- Divided the application into three major modules: ingestion, database management, and web interface.
- Identified the required entities and relationships for the database design.

**Technical Decisions:**

- Adopted a modular project structure.
- Selected PostgreSQL for persistent relational storage.
- Decided to use JSON payloads for testing ingestion independently of external API availability.

**Outcome:**

The overall architecture and development roadmap were established.

---

## Day 2 – Development Environment Setup

**Objective:** Configure the development environment and install the required software.

**Work Performed:**

- Installed and configured Python.
- Created a Python virtual environment for dependency isolation.
- Installed PostgreSQL 18 and configured its command-line utilities.
- Resolved the Windows PATH configuration required to access PostgreSQL commands.
- Installed the Python dependencies listed in `requirements.txt`.
- Created the `.env` configuration file for database credentials and API authentication.

**Challenges:**

Initially, PostgreSQL commands were not recognized by the Windows terminal because its binary directory was not available through PATH.

**Resolution:**

Configured the PostgreSQL `bin` directory in the Windows environment variables and verified the installation using `psql --version`.

**Outcome:**

The development environment and PostgreSQL command-line tools were configured successfully.

---

## Day 3 – Database Design and Schema Implementation

**Objective:** Implement the normalized relational database schema.

**Work Performed:**

- Analysed the entities specified in the assignment.
- Designed five relational tables: `users`, `tweets`, `hashtags`, `topics`, and `tweet_topics`.
- Defined primary keys and foreign key relationships.
- Implemented the schema in `db/create_schema.sql`.
- Created the PostgreSQL database named `tweetsdb`.
- Executed the schema file using the PostgreSQL command-line utility.
- Verified the successful creation of all five tables.

**Technical Decisions:**

- Used `TEXT` identifiers for users and tweets.
- Used a composite primary key for the hashtag association table.
- Used a junction table to maintain the many-to-many relationship between topics and tweets.
- Used timestamps and Boolean fields where appropriate.

**Outcome:**

The PostgreSQL database was created successfully with all five required tables.

---

## Day 4 – Database Connectivity and Configuration

**Objective:** Establish connectivity between the Python application and PostgreSQL.

**Work Performed:**

- Configured the PostgreSQL connection string through the `.env` file.
- Integrated the database configuration with the Python ingestion module.
- Tested the database connection through the Python application.
- Investigated connection failures caused by special characters in the database password.
- Corrected the connection string by encoding the special characters appropriately.
- Verified that the Python application could communicate with PostgreSQL.

**Challenges:**

A connection error occurred because a special character in the password was interpreted incorrectly within the database URL.

**Resolution:**

Corrected the connection string using URL encoding and verified successful connectivity.

**Outcome:**

Python-to-PostgreSQL connectivity was established.

---

## Day 5 – Mock Data Generation and JSON Processing

**Objective:** Develop and validate the ingestion workflow using mock tweet data.

**Work Performed:**

- Inspected the expected structure of an X API v2 response.
- Studied the relationship between tweet data and expanded user information.
- Used the provided sample JSON payload for initial testing.
- Generated a smaller assignment-specific mock payload containing five dummy tweets from three dummy users.
- Included tweet identifiers, author identifiers, content, timestamps, language, engagement metrics, and hashtags.
- Prepared topic information for associating ingested tweets with their corresponding search query.

**Technical Decisions:**

The mock payload was designed to resemble the general structure of an X API v2 search response. This allowed the ingestion workflow to be tested without making external API requests.

**Outcome:**

A reusable mock-data testing approach was established.

---

## Day 6 – Data Ingestion and Database Population

**Objective:** Process JSON tweet records and populate the normalized PostgreSQL database.

**Work Performed:**

- Executed the Python ingestion script in mock mode.
- Processed the supplied sample payload.
- Extracted tweet and user information.
- Processed hashtag associations.
- Stored the corresponding records in PostgreSQL.
- Recorded topic-to-tweet associations.
- Verified the ingestion output and database connectivity.

**Observed Results:**

The initial sample ingestion reported:

| Metric                  | Records |
| ----------------------- | ------: |
| Tweets upserted         |      72 |
| Users upserted          |      12 |
| Hashtag links processed |     161 |
| API requests            |       0 |
| Rate-limit waits        |       0 |

**Outcome:**

The mock ingestion pipeline successfully processed the supplied sample dataset.

---

## Day 7 – X API Authentication and Live Ingestion Testing

**Objective:** Configure X API authentication and investigate live tweet collection.

**Work Performed:**

- Created an X Developer application.
- Generated an application Bearer Token.
- Configured the token through the `.env` file.
- Inspected the ingestion script's command-line arguments.
- Executed the ingestion script without the mock-file argument to activate live API mode.
- Tested a search query for generative AI.

**Challenges:**

The application successfully reached the X API, but the request returned HTTP 402 with the error `credits_depleted`.

This indicated that the developer account did not have sufficient API credits for the requested operation.

**Resolution and Decision:**

Avoided unnecessary API expenditure and retained the mock ingestion workflow for application development and demonstration.

**Outcome:**

The live API authentication and request workflow was attempted, but successful live data retrieval remains dependent on API credit availability.

---

## Day 8 – Flask Application and Database Query Integration

**Objective:** Develop and validate the web-based tweet search interface.

**Work Performed:**

- Inspected the Flask application structure.
- Configured the application entry point at `web/app.py`.
- Connected the web application to the PostgreSQL database.
- Reviewed the search form parameters.
- Identified the required search fields: tweet content, hashtag, username, and date range.
- Reviewed the SQL query construction and result rendering workflow.
- Prepared the application to run locally from the project root.

**Technical Considerations:**

- Used parameterized SQL queries to safely process search inputs.
- Used joins to retrieve tweet and user information.
- Used aggregation to display associated hashtags.
- Used result limits to prevent unnecessarily large responses.

**Outcome:**

The Flask application and database-query workflow were prepared for local execution and validation.

*Record the successful browser testing result here after completing the end-to-end verification.*

---

## Day 9 – Repository Organization and Documentation

**Objective:** Organize the source code and prepare the project for version control.

**Work Performed:**

- Organized the project into database, ingestion, and web application modules.
- Prepared the `.gitignore` file.
- Excluded environment credentials and virtual environment directories from version control.
- Retained `.env.example` as a template for reproducible configuration.
- Reviewed the source-code structure.
- Prepared the README documentation covering architecture, installation, database design, and execution instructions.

**Technical Decisions:**

- Kept sensitive credentials outside the repository.
- Retained mock JSON payloads for reproducible testing.
- Separated project documentation from assignment-specific submission material.

**Outcome:**

The repository structure and project documentation were organized for GitHub submission.

---

## Day 10 – Testing, Validation and Assignment Preparation

**Objective:** Validate the complete application workflow and prepare the final assignment submission.

**Work Performed:**

- Reviewed the PostgreSQL schema and its relationships.
- Verified the mock ingestion workflow.
- Prepared SQL queries for checking stored users, tweets, hashtags, and topic associations.
- Reviewed the Flask search functionality.
- Prepared a list of screenshots required to demonstrate the project.
- Organized the technical report around the database schema, ingestion approach, and web application.
- Reviewed the README and setup instructions.

**Final Validation Checklist:**

- [x] Python environment configured.
- [ ] PostgreSQL installed and configured.
- [x] Database created.
- [ ] Five database tables created.
- [ ] Mock ingestion successfully executed.
- [ ] Sample tweet records processed.
- [ ] Live X API ingestion successfully tested.
- [ ] Flask search interface tested end to end.
- [ ] Final assignment screenshots captured.
- [ ] Final report and PDF prepared.

**Outcome:**

The database and mock ingestion components were validated. Remaining work involves final end-to-end web validation and preparation of the assignment submission.

---

## Overall Development Summary

The project progressed from requirement analysis and environment setup to relational database implementation, Python-based ingestion, and web application integration.

A normalized PostgreSQL schema was implemented according to the assignment specification. The mock ingestion workflow was successfully tested using JSON data, demonstrating the ability to process tweet records and maintain the corresponding user, hashtag, and topic relationships.

Live X API testing was attempted, but further execution requires sufficient API credits. The mock-data workflow provides a reproducible alternative for validating the application's database and search functionality.

The project establishes a modular foundation for collecting, storing, and querying topic-specific social media data.

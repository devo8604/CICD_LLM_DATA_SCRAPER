# LLM Data Pipeline

This project is a data pipeline for processing source code from Git repositories and generating question-and-answer pairs for training Large Language Models (LLMs).

## Table of Contents

- [LLM Data Pipeline](#llm-data-pipeline)
  - [Table of Contents](#table-of-contents)
  - [Project Overview](#project-overview)
  - [Directory Structure](#directory-structure)
  - [Dependencies](#dependencies)
  - [Quickstart](#quickstart)
  - [Usage](#usage)
    - [Scrape](#scrape)
    - [Prepare](#prepare)
    - [Retry](#retry)
  - [Database Schema](#database-schema)
    - [TrainingSamples](#trainingsamples)
    - [ConversationTurns](#conversationturns)
    - [FileHashes](#filehashes)
    - [FailedFiles](#failedfiles)

## Project Overview

The pipeline is designed to automate the process of collecting and preparing training data for LLMs from a large number of source code files. It consists of the following main stages:

1.  **Scraping:** Clones or updates a list of Git repositories from a given list of URLs.
2.  **Preparation:** Traverses the downloaded repositories, processes each file, and generates question-and-answer pairs using an LLM.
3.  **Data Storage:** Stores the generated Q&A pairs, along with file hashes and other metadata, in a SQLite database.
4.  **Error Handling:** Tracks files that fail to process and provides a mechanism to retry them later.

## Directory Structure

```
.
├── data/
│   └── pipeline.db
├── logs/
├── repos/
├── src/
│   ├── cli.py
│   ├── data_pipeline.py
│   ├── db_manager.py
│   └── ...
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

-   `data/`: Contains the SQLite database (`pipeline.db`) where all the generated data is stored.
-   `logs/`: Contains log files for each run of the pipeline.
-   `repos/`: The directory where the Git repositories are cloned.
-   `src/`: Contains the source code for the pipeline.
-   `main.py`: The main entry point for the application.
-   `requirements.txt`: A list of the Python dependencies required to run the project.

## Dependencies

The project's dependencies are listed in the `requirements.txt` file. To install them, run:

```bash
pip install -r requirements.txt
```

## Quickstart

1.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Create a `repos.txt` file** in the root of the project and add a list of Git repository URLs to it, one URL per line.

3.  **Run the scrape command** to clone the repositories:

    ```bash
    python3 main.py scrape
    ```

4.  **Run the prepare command** to process the files and generate Q&A pairs:

    ```bash
    python3 main.py prepare
    ```

## Usage

The application is controlled via command-line arguments.

### Scrape

The `scrape` command clones or updates the repositories listed in `repos.txt`.

```bash
python3 main.py scrape
```

### Prepare

The `prepare` command processes the files in the `repos` directory and generates question-and-answer pairs.

```bash
python3 main.py prepare
```

You can customize the behavior of the `prepare` command with the following options:

-   `--max-tokens`: Maximum number of tokens for LLM generated answers.
-   `--temperature`: Sampling temperature for LLM generated questions.
-   `--max-file-size`: Maximum size of a file (in bytes) to be processed.

### Retry

The `retry` command attempts to re-process any files that failed during the `prepare` stage.

```bash
python3 main.py retry
```

## Database Schema

The pipeline uses a SQLite database to store its data. The schema is defined in `src/training_data_repository.py` and consists of the following tables:

### TrainingSamples

Stores information about each generated Q&A sample.

| Column               | Type      | Description                               |
| -------------------- | --------- | ----------------------------------------- |
| `sample_id`          | `INTEGER` | Primary key                               |
| `dataset_source`     | `VARCHAR` | The source of the data (e.g., file path)  |
| `creation_date`      | `TIMESTAMP`| When the sample was created               |
| `model_type_intended`| `VARCHAR` | The intended model type for the sample    |
| `sample_quality_score`| `REAL`    | A score representing the quality of the sample |
| `is_multiturn`       | `BOOLEAN` | Whether the sample is part of a multi-turn conversation |

### ConversationTurns

Stores the individual turns of a conversation for each sample.

| Column         | Type      | Description                               |
| -------------- | --------- | ----------------------------------------- |
| `turn_id`      | `INTEGER` | Primary key                               |
| `sample_id`    | `INTEGER` | Foreign key to `TrainingSamples`          |
| `turn_index`   | `INTEGER` | The order of the turn in the conversation |
| `role`         | `VARCHAR` | The role of the speaker (e.g., 'user', 'assistant') |
| `content`      | `TEXT`    | The text of the turn                      |
| `is_label`     | `BOOLEAN` | Whether the turn is a label               |
| `metadata_json`| `TEXT`    | Additional metadata in JSON format        |

### FileHashes

Stores the hash of each processed file to avoid reprocessing unchanged files.

| Column         | Type      | Description                               |
| -------------- | --------- | ----------------------------------------- |
| `file_path`    | `TEXT`    | Primary key, the path to the file         |
| `content_hash` | `TEXT`    | The SHA256 hash of the file content       |
| `last_processed`| `DATETIME`| When the file was last processed          |
| `sample_id`    | `INTEGER` | Foreign key to `TrainingSamples`          |

### FailedFiles

Stores information about files that failed to process.

| Column      | Type      | Description                               |
| ----------- | --------- | ----------------------------------------- |
| `failed_id` | `INTEGER` | Primary key                               |
| `file_path` | `TEXT`    | The path to the failed file               |
| `reason`    | `TEXT`    | The reason for the failure                |
| `failed_at` | `TIMESTAMP`| When the failure occurred                 |

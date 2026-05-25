# Howler Demo

This directory contains a `docker-compose.yml` file to quickly spin up a demonstration environment for Howler.

This setup includes:
- Howler API
- Howler UI
- Elasticsearch
- Redis
- Kibana
- A data seeder to populate the instance with sample data.

## Prerequisites

- Docker
- Docker Compose

## Getting Started

1.  **Boot the environment:**
    Open a terminal in this directory (`demo/`) and run the following command:
    ```bash
    docker compose up -d
    ```
    This will download the required images and start all the services in the background. The initial startup may take a few minutes while the data seeder populates Elasticsearch with sample hits, users, and other data.

2.  **Access Howler:**
    Once the services are running, you can access the Howler UI in your browser at:
    [http://localhost:8080](http://localhost:8080)

## Logging In

The data seeder creates a set of default users for you to use. You can log in with any of the following accounts:

| Username  | Password  | Role    |
|-----------|-----------|---------|
| `admin`   | `admin`   | Admin   |
| `user`    | `user`    | User    |
| `shawn-h` | `shawn-h` | Admin   |
| `goose`   | `goose`   | Admin   |
| `huey`    | `huey`    | User    |

The `admin` user has full administrator privileges.

## Shutting Down

To stop and remove the containers, run the following command from this directory:
```bash
docker compose down
```

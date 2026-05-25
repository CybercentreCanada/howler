# Client Development

If you want to contribute to the Howler client development, you'll need to set up the development environment.

## Development Setup

The client code is located in the `client/` folder of the Howler monorepo. To set up for development:

```bash
cd ~/repos/howler/client

# Install Poetry if you don't have it
python3 -m pip install poetry

# Configure Poetry to create virtualenv in project directory
poetry config virtualenvs.in-project true

# Install dependencies including test dependencies
poetry install --with test
```

## Running Tests

The client has a comprehensive test suite that runs against a live Howler instance:

```bash
# Start test dependencies (API, Elasticsearch, Redis) using Docker Compose
docker compose -f test/docker-compose.yml up -d

# Wait for services to be ready, then run tests
poetry run test
```

The tests are located in `client/test/` and include:

- Unit tests for client functionality
- Integration tests against the API

## Code Quality

Before submitting changes, ensure your code passes all quality checks:

```bash
# Run formatting checks
poetry run ruff format howler_client --diff

# Run linter checks
poetry run ruff check howler_client

# Run type checking
poetry run type_check
```

## Running Specific Tests

You can run specific test files or test functions:

```bash
# Run a specific test file
poetry run pytest test/integration/test_hit.py

# Run a specific test function
poetry run pytest test/integration/test_hit.py::test_create

# Run with verbose output
poetry run pytest test/integration/test_hit.py -v
```

## Additional Resources

- **API Documentation**: Explore the full API at `https://your-howler-instance.com/api/doc`
- **Howler Schema**: View the hit schema in the UI under Help → Hit Schema
- **GitHub Repository**: [https://github.com/CybercentreCanada/howler](https://github.com/CybercentreCanada/howler)
- **PyPI Package**: [https://pypi.org/project/howler-client/](https://pypi.org/project/howler-client/)
- **Issue Tracker**: Report bugs or request features on [GitHub Issues](https://github.com/CybercentreCanada/howler/issues)

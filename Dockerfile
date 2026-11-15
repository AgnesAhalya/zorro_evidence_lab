FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --retries 5 -e '.[live]'

COPY config ./config
COPY prompts ./prompts
COPY data ./data
COPY pilot ./pilot
COPY tests ./tests
COPY docs ./docs

RUN useradd --create-home --uid 10001 zorro \
    && chown -R zorro:zorro /app

USER zorro

CMD ["python", "-m", "crimino_flipper.cli", "show-plan"]

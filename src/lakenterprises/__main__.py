"""LakEnterprises – CLI entry point.

Run as a module::

    python -m lakenterprises research "How does LangGraph work?"

Or via the installed console script::

    lakenterprises research "How does LangGraph work?"

Subcommands
-----------
research  Run a research query (default).
demo      Run the canonical demo question.
validate  Validate environment configuration.
serve     Start a FastAPI server (Phase 3 stub).
"""

import argparse
import logging
import sys

from .config import Settings, get_settings, setup_logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical demo question
# ---------------------------------------------------------------------------

CANONICAL_DEMO_QUESTION: str = (
    "Which customers were impacted by the Payments API last quarter, "
    "what incidents occurred, which teams own those services, and "
    "what decisions were taken to prevent recurrence?"
)

# ---------------------------------------------------------------------------
# Subcommand: research
# ---------------------------------------------------------------------------


def _cmd_research(args: argparse.Namespace, settings: Settings) -> None:
    """Execute a research query through the pipeline."""
    query: str = args.query
    provider: str = getattr(args, "provider", None) or settings.llm_provider
    model: str = getattr(args, "model", None) or settings.llm_model

    logger.info("Research query: %s (provider=%s, model=%s)", query, provider, model)

    # ── Build LLM ──────────────────────────────────────────────────────
    from .llm import get_llm

    llm = get_llm(provider=provider, model=model)

    # ── Build & run pipeline ───────────────────────────────────────────
    from .pipeline import create_research_pipeline

    pipeline = create_research_pipeline(llm)

    initial_state: dict = {
        "query": query,
    }

    try:
        response = pipeline.run(initial_state)
    except Exception as exc:  # pragma: no cover – real LLM failures
        logger.error("Pipeline error: %s", exc, exc_info=True)
        print(f"\nError during research: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Print results ──────────────────────────────────────────────────
    if response.error:
        print(f"\nError: {response.error}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Query:  {query}")
    print(f"{'='*60}\n")
    print(response.answer)

    if response.citations:
        print(f"\n{'─'*60}")
        print("  Citations")
        print(f"{'─'*60}")
        for i, cite in enumerate(response.citations, 1):
            print(f"  [{i}] {cite}")

    if response.metadata:
        print(f"\n{'─'*60}")
        print("  Run Metadata")
        print(f"{'─'*60}")
        for key, value in response.metadata.items():
            print(f"  {key}: {value}")

    print()


# ---------------------------------------------------------------------------
# Subcommand: demo
# ---------------------------------------------------------------------------


def _cmd_demo(args: argparse.Namespace, settings: Settings) -> None:
    """Run the canonical demo question."""
    print(f"Running canonical demo question:\n  {CANONICAL_DEMO_QUESTION}\n")

    # Reuse the research command with the canonical question
    fake_args = argparse.Namespace(
        query=CANONICAL_DEMO_QUESTION,
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
    )
    _cmd_research(fake_args, settings)


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------


def _cmd_validate(_args: argparse.Namespace, settings: Settings) -> None:
    """Validate the environment configuration and print a summary."""
    print("LakEnterprises Configuration Validator")
    print("=" * 50)

    issues: list[str] = []
    warnings: list[str] = []

    # ── Core LLM settings ──────────────────────────────────────────────
    _check("LLM Provider", settings.llm_provider, issues)
    _check("LLM Model", settings.llm_model, issues)
    _check("Embedding Model", settings.embedding_model, issues)

    # ── Vector store ───────────────────────────────────────────────────
    _check("Vector Store Type", settings.vector_store_type, issues)
    _check("Vector Store Path", settings.vector_store_path, issues)

    # ── Database ───────────────────────────────────────────────────────
    _check("Database URL", settings.db_url, issues)

    # ── Graph store ────────────────────────────────────────────────────
    _check("Graph Store Type", settings.graph_store_type, issues)
    _check("Graph URI", settings.graph_uri, issues)

    # ── Redis ──────────────────────────────────────────────────────────
    _check("Redis URL", settings.redis_url, issues)

    # ── API keys (conditional) ─────────────────────────────────────────
    provider = settings.llm_provider
    key_map: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "cohere": "COHERE_API_KEY",
        "watsonx": "WATSONX_APIKEY",
    }

    if provider in key_map:
        env_name = key_map[provider]
        # Check if the key is set (non-empty)
        import os

        key_value = os.environ.get(env_name, "")
        if key_value:
            print(f"  [OK]   {env_name}")
        else:
            issues.append(f"{env_name} is not set (required for provider '{provider}')")

    if provider == "azure":
        if not settings.azure_openai_endpoint:
            issues.append("AZURE_OPENAI_ENDPOINT is not set")
        else:
            print("  [OK]   AZURE_OPENAI_ENDPOINT")

    if provider == "watsonx":
        if not settings.watsonx_url:
            issues.append("WATSONX_URL is not set")
        else:
            print("  [OK]   WATSONX_URL")

    if provider == "ollama":
        print(f"  [INFO] Ollama base URL: {settings.ollama_base_url}")
        warnings.append(
            "Ollama provider requires a running Ollama server; "
            f"checked URL: {settings.ollama_base_url}"
        )

    # ── Graph password ─────────────────────────────────────────────────
    if settings.graph_store_type == "neo4j":
        import os

        pwd = os.environ.get("GRAPH_PASSWORD", "")
        if pwd:
            print("  [OK]   GRAPH_PASSWORD")
        else:
            issues.append("GRAPH_PASSWORD is not set (required for Neo4j)")

    # ── Feature flags ──────────────────────────────────────────────────
    _check("Log Level", settings.log_level, issues)
    _check("Log Format", settings.log_format, issues)
    _check("Retrieval Top-K (str)", str(settings.retrieval_top_k), issues)
    _check("Rerank Model", settings.rerank_model, issues)

    # ── API server (Phase 3) ───────────────────────────────────────────
    print(f"  [INFO] API Host: {settings.api_host}")
    print(f"  [INFO] API Port: {settings.api_port}")
    warnings.append("API server is not yet implemented (Phase 3)")

    # ── Feature flags ──────────────────────────────────────────────────
    print(f"  [INFO] Debug mode: {settings.debug_mode}")
    print(f"  [INFO] Graph RAG enabled: {settings.enable_graphrag}")
    print(f"  [INFO] Guardrails enabled: {settings.enable_guardrails}")

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print("  Settings Summary")
    print(f"{'='*50}")
    print(settings)

    if issues:
        print(f"\n{'='*50}")
        print(f"  Issues ({len(issues)})")
        print(f"{'='*50}")
        for issue in issues:
            print(f"  [FAIL] {issue}")
    else:
        print("\n  No configuration issues found.")

    if warnings:
        print(f"\n{'='*50}")
        print(f"  Warnings ({len(warnings)})")
        print(f"{'='*50}")
        for warning in warnings:
            print(f"  [WARN] {warning}")

    print()

    if issues:
        print(
            f"Configuration validation FAILED with {len(issues)} issue(s).",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print("Configuration validation PASSED.")


def _check(label: str, value: str, issues: list[str]) -> None:
    """Print a check result and record issues for missing values."""
    if value:
        print(f"  [OK]   {label}: {value}")
    else:
        issues.append(f"{label} is not set")


# ---------------------------------------------------------------------------
# Subcommand: serve
# ---------------------------------------------------------------------------


def _cmd_serve(args: argparse.Namespace, _settings: Settings) -> None:
    """Start the FastAPI server."""
    import uvicorn

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8001)
    print(f"Starting LakEnterprises API server on {host}:{port}")
    uvicorn.run("lakenterprises.app:app", host=host, port=port, reload=False)


def _cmd_ingest(args: argparse.Namespace, _settings: Settings) -> None:
    """Ingest a document or directory of documents."""
    from pathlib import Path

    from lakenterprises.services.document import DocumentService

    path = Path(args.path)
    if not path.exists():
        print(f"Error: path '{path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    service = DocumentService()
    files = (
        [path]
        if path.is_file()
        else sorted([p for p in path.glob("**/*") if p.is_file()])
    )

    if not files:
        print(f"No files found to ingest in {path}.")
        return

    print(f"Ingesting {len(files)} file(s)...")
    total_chunks = 0
    for f in files:
        try:
            doc_name = args.name if (len(files) == 1 and args.name) else f.name
            doc, chunks = service.ingest_file(
                f,
                name=doc_name,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
            total_chunks += len(chunks)
            print(f"  [OK] Ingested '{doc.name}' (ID: {doc.id}, {len(chunks)} chunks)")
        except Exception as exc:
            print(f"  [FAIL] Failed to ingest '{f.name}': {exc}", file=sys.stderr)

    print(f"Done. Ingested {len(files)} document(s) with {total_chunks} total chunks.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="lakenterprises",
        description="LakEnterprises – enterprise knowledge research platform",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        description="Available commands",
    )

    # ── research (default) ─────────────────────────────────────────────
    research_parser = subparsers.add_parser(
        "research",
        help="Run a research query",
        description="Run a research query through the multi-step pipeline.",
    )
    research_parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="The research question to investigate.",
    )
    research_parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider (overrides LLM_PROVIDER in settings).",
    )
    research_parser.add_argument(
        "--model",
        default=None,
        help="LLM model name (overrides LLM_MODEL in settings).",
    )

    # ── demo ───────────────────────────────────────────────────────────
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run the canonical demo question",
        description=f'Run the canonical demo question: "{CANONICAL_DEMO_QUESTION}"',
    )
    demo_parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider (overrides LLM_PROVIDER in settings).",
    )
    demo_parser.add_argument(
        "--model",
        default=None,
        help="LLM model name (overrides LLM_MODEL in settings).",
    )

    # ── validate ───────────────────────────────────────────────────────
    subparsers.add_parser(
        "validate",
        help="Validate environment configuration",
        description="Check .env, required keys, and print a settings summary.",
    )

    # ── serve ──────────────────────────────────────────────────────────
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start FastAPI server",
        description="Start the FastAPI API server on the configured host and port.",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to listen on (default: 8001).",
    )

    # ── ingest ─────────────────────────────────────────────────────────
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest and chunk documents into the knowledge base",
        description="Ingest files, split into chunks, persist to DB, and index into vector store.",
    )
    ingest_parser.add_argument(
        "path",
        help="File or directory path to ingest.",
    )
    ingest_parser.add_argument(
        "--name",
        default=None,
        help="Document name (applies only when ingesting a single file).",
    )
    ingest_parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Target chunk size in characters (default: 500).",
    )
    ingest_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Chunk overlap in characters (default: 50).",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point.

    Parameters
    ----------
    argv:
        Override ``sys.argv[1:]`` for testing.  When ``None``, uses
        the real command-line arguments.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Load settings & configure logging ──────────────────────────────
    settings = get_settings()
    setup_logging()

    # ── Dispatch ───────────────────────────────────────────────────────
    command = args.command

    if command == "research" or command is None:
        # Default to research
        if args.query is None:
            parser.error("the following arguments are required: query")
        _cmd_research(args, settings)

    elif command == "demo":
        _cmd_demo(args, settings)

    elif command == "validate":
        _cmd_validate(args, settings)

    elif command == "serve":
        _cmd_serve(args, settings)

    elif command == "ingest":
        _cmd_ingest(args, settings)

    else:
        parser.print_help()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Module-level entry: ``python -m lakenterprises``
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)  # SIGINT exit code

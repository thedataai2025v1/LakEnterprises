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


def _cmd_process(args: argparse.Namespace, _settings: Settings) -> None:
    """Manage process templates, instances, tasks, and execute process demos."""
    from lakenterprises.db import get_db_session
    from lakenterprises.services.approval import ApprovalService
    from lakenterprises.services.process import ProcessService

    action = getattr(args, "action", None)
    if not action:
        print(
            "Please specify a process action: list, start, status, or run-demo.",
            file=sys.stderr,
        )
        sys.exit(1)

    with get_db_session() as session:
        proc_service = ProcessService(session)
        appr_service = ApprovalService(session)

        if action == "list":
            templates = proc_service.list_templates()
            print(f"\nFound {len(templates)} Process Template(s):")
            for tpl in templates:
                status_str = "ACTIVE" if tpl.is_active else "INACTIVE"
                print(f"  • [{tpl.id[:8]}] {tpl.name} (v{tpl.version}, {status_str})")
                steps = tpl.definition.get("steps", []) if tpl.definition else []
                print(
                    f"      Steps ({len(steps)}): {', '.join(s.get('name', 'Step') for s in steps)}"
                )

        elif action == "start":
            tpl_id = args.template_id
            if not tpl_id:
                # Find first active template or by name
                templates = proc_service.list_templates(active_only=True)
                if not templates:
                    print("No active templates found to start.", file=sys.stderr)
                    sys.exit(1)
                tpl_id = templates[0].id

            inst = proc_service.start_process(
                template_id=tpl_id,
                title=args.title or "CLI Executed Process",
            )
            print(f"[OK] Started process instance '{inst.title}' (ID: {inst.id})")
            tasks = proc_service.get_instance_tasks(inst.id)
            print(f"     Materialized {len(tasks)} tasks.")

        elif action == "status":
            inst_id = args.instance_id
            if not inst_id:
                print(
                    "Error: --instance-id is required for 'status' action.",
                    file=sys.stderr,
                )
                sys.exit(1)
            inst = proc_service.get_instance(inst_id)
            if not inst:
                print(
                    f"Error: Process instance '{inst_id}' not found.", file=sys.stderr
                )
                sys.exit(1)
            print(f"\nProcess Instance: {inst.title} [{inst.status.upper()}]")
            print(f"Template ID:      {inst.template_id}")
            print(f"Instance ID:      {inst.id}")
            print("\nTasks:")
            tasks = proc_service.get_instance_tasks(inst.id)
            for t in tasks:
                print(
                    f"  [{t.position + 1}] {t.name} -> {t.status.upper()} (role: {t.assignee_role or 'any'})"
                )

        elif action == "run-demo":
            print("\n=== Running Canonical Enterprise Process Demo ===")
            # 1. Create or retrieve demo template
            tpl_name = "Quarterly Incident Review & Root Cause Process"
            tpl = proc_service.get_template_by_name(tpl_name)
            if not tpl:
                print("1. Creating Process Template...")
                tpl = proc_service.create_template(
                    name=tpl_name,
                    description=(
                        "Standard enterprise workflow for incident post-mortem, review, and resolution sign-off."
                    ),
                    definition={
                        "steps": [
                            {"name": "Extract Incident Data", "role": "analyst"},
                            {"name": "Analyze Service Impact", "role": "analyst"},
                            {"name": "Executive Sign-off Gate", "role": "manager"},
                            {"name": "Publish Post-Mortem Report", "role": "admin"},
                        ]
                    },
                )
            print(f"  [OK] Using Template: {tpl.name} (ID: {tpl.id})")

            # 2. Start process instance
            print("\n2. Instantiating Process...")
            inst = proc_service.start_process(
                template_id=tpl.id,
                title="Q3 Payments Outage Review",
                context={"quarter": "Q3", "severity": "HIGH"},
            )
            print(
                f"  [OK] Process Instance Created: {inst.title} (Status: {inst.status})"
            )

            # 3. Progress through step 1 and step 2
            tasks = proc_service.get_instance_tasks(inst.id)
            print(f"\n3. Progressing Initial Tasks ({len(tasks)} total)...")
            proc_service.update_task_status(tasks[0].id, "in_progress")
            proc_service.update_task_status(
                tasks[0].id, "completed", result={"records_extracted": 42}
            )
            print(f"  • Task 1 '{tasks[0].name}' COMPLETED")

            proc_service.update_task_status(tasks[1].id, "in_progress")
            proc_service.update_task_status(
                tasks[1].id,
                "completed",
                result={"root_cause": "Database connection pool exhaustion"},
            )
            print(f"  • Task 2 '{tasks[1].name}' COMPLETED")

            # 4. Trigger Approval Gate for Step 3
            print("\n4. Triggering Human-in-the-Loop Approval Gate...")
            approval = appr_service.request_approval(
                target_type="process_instance",
                target_id=inst.id,
                action="executive_signoff",
                requested_by_id="analyst-system-user",
            )
            print(f"  • Approval Request ID: {approval.id} (Status: {approval.status})")

            # Simulate Manager Review & Approval
            reviewed = appr_service.approve(
                request_id=approval.id,
                reviewed_by_id="manager-admin-user",
                comment="Root cause analysis verified. Remediation actions approved for deployment.",
            )
            print(
                f"  • Approval Granted by {reviewed.reviewed_by_id}: {reviewed.comment}"
            )

            # 5. Complete Final Task & Transition Instance
            print("\n5. Completing Process Lifecycle...")
            proc_service.update_task_status(
                tasks[2].id, "completed", result={"approved": True}
            )
            proc_service.update_task_status(tasks[3].id, "in_progress")
            proc_service.update_task_status(
                tasks[3].id,
                "completed",
                result={
                    "report_url": "https://lakenterprises.internal/reports/q3-incident"
                },
            )
            print(f"  • Task 4 '{tasks[3].name}' COMPLETED")

            final_inst = proc_service.transition_instance(inst.id, "completed")
            print(
                f"\n[SUCCESS] Process Lifecycle Finished! Final Instance Status: {final_inst.status.upper()}"
            )


# ---------------------------------------------------------------------------
# Subcommand: tools
# ---------------------------------------------------------------------------


def _cmd_tools(args: argparse.Namespace, settings: Settings) -> None:
    """Manage and execute agent tools."""
    import json

    from .tools import ToolExecutor, default_registry, register_default_tools

    register_default_tools(default_registry)
    executor = ToolExecutor(registry=default_registry)
    action = args.action

    if action == "list":
        tools = default_registry.list_tools()
        print(f"\nRegistered Agent Tools ({len(tools)} total):")
        print("=" * 80)
        print(
            f"{'Tool Name':<28} {'Category':<10} {'Risk':<10} {'Approval':<10} {'Description'}"
        )
        print("-" * 80)
        for t in tools:
            appr_str = "Yes" if t.requires_approval else "No"
            print(
                f"{t.name:<28} {t.category.value:<10} {t.risk_level.value:<10} {appr_str:<10} {t.description[:60]}"
            )
        print()

    elif action == "inspect":
        tool_name = getattr(args, "tool_name", None)
        if not tool_name:
            print("Error: --tool-name is required for 'inspect'.", file=sys.stderr)
            sys.exit(1)
        tool = default_registry.get(tool_name)
        if not tool:
            print(f"Error: Tool '{tool_name}' not found.", file=sys.stderr)
            sys.exit(1)
        defn = tool.get_definition()
        print(f"\nTool Specification: {tool.name}")
        print("=" * 60)
        print(f"Description:        {defn.description}")
        print(f"Category:           {defn.category.value}")
        print(f"Risk Level:         {defn.risk_level.value}")
        print(f"Requires Approval:  {defn.requires_approval}")
        print(f"Allowed Roles:      {', '.join(defn.allowed_roles)}")
        print("\nParameters Schema:")
        print(json.dumps(defn.parameters_schema, indent=2))
        print()

    elif action == "run":
        tool_name = getattr(args, "tool_name", None)
        if not tool_name:
            print("Error: --tool-name is required for 'run'.", file=sys.stderr)
            sys.exit(1)
        raw_params = getattr(args, "params", "{}") or "{}"
        try:
            params = json.loads(raw_params)
        except Exception as exc:
            print(f"Error parsing JSON params: {exc}", file=sys.stderr)
            sys.exit(1)

        roles = [
            r.strip() for r in (getattr(args, "roles", "admin") or "admin").split(",")
        ]
        user_id = getattr(args, "user_id", "cli_user") or "cli_user"
        approval_id = getattr(args, "approval_id", None)

        print(f"Executing tool '{tool_name}' as {roles}...")
        result = executor.execute(
            tool_name=tool_name,
            parameters=params,
            user_roles=roles,
            user_id=user_id,
            approval_id=approval_id,
        )

        print(f"\nExecution Result: {'SUCCESS' if result.success else 'FAILED'}")
        print("=" * 60)
        print(f"Success:            {result.success}")
        print(f"Execution Time:     {result.execution_time_ms} ms")
        print(f"Requires Approval:  {result.requires_approval}")
        if result.approval_request_id:
            print(f"Approval Request:   {result.approval_request_id}")
        if result.error:
            print(f"Error / Reason:     {result.error}")
        if result.output is not None:
            print("\nOutput:")
            if isinstance(result.output, (dict, list)):
                print(json.dumps(result.output, indent=2))
            else:
                print(result.output)
        print()


# ---------------------------------------------------------------------------
# Subcommand: guardrails
# ---------------------------------------------------------------------------


def _cmd_guardrails(args: argparse.Namespace, settings: Settings) -> None:
    """Inspect and run guardrails security operations."""
    import json

    from .guardrails import (
        default_injection_guard,
        default_rules_engine,
        default_scrubber,
    )

    action = args.action

    if action == "scrub":
        raw_text = getattr(args, "text", "") or ""
        if not raw_text:
            print("Error: --text is required for 'scrub'.", file=sys.stderr)
            sys.exit(1)
        res = default_scrubber.scrub_text(raw_text)
        print("\nPII & Secret Scrubber Results:")
        print("=" * 60)
        print(f"Contains PII:       {res.contains_pii}")
        print(f"Contains Secrets:   {res.contains_secrets}")
        print(f"Detections Count:   {len(res.detections)}")
        if res.detections:
            print("\nDetections:")
            for d in res.detections:
                print(f"  - [{d.entity_type}]: {d.original_snippet} -> {d.replacement}")
        print("\nScrubbed Output:")
        print(res.scrubbed_text)
        print()

    elif action == "check":
        raw_text = getattr(args, "text", "") or ""
        if not raw_text:
            print("Error: --text is required for 'check'.", file=sys.stderr)
            sys.exit(1)
        strict = getattr(args, "strict", False)
        res = default_injection_guard.check(raw_text, strict=strict)
        print("\nPrompt Injection Evaluation:")
        print("=" * 60)
        print(f"Is Injected:        {res.is_injected}")
        print(f"Risk Score:         {res.risk_score}")
        print(f"Risk Level:         {res.risk_level}")
        print(f"Matched Patterns:   {res.matched_patterns}")
        print("\nSanitized Input Wrapper:")
        print(res.sanitized_text)
        print()

    elif action == "evaluate":
        event_type = getattr(args, "event_type", "INCIDENT") or "INCIDENT"
        raw_payload = getattr(args, "payload", "{}") or "{}"
        try:
            payload = json.loads(raw_payload)
        except Exception as exc:
            print(f"Error parsing JSON payload: {exc}", file=sys.stderr)
            sys.exit(1)
        decision = default_rules_engine.evaluate(event_type=event_type, payload=payload)
        print("\nSeverity & Escalation Evaluation:")
        print("=" * 60)
        print(f"Severity Tier:      {decision.severity.value}")
        print(f"Should Escalate:    {decision.should_escalate}")
        print(f"Requires Pager:     {decision.requires_immediate_pager}")
        print(f"Assigned Role:      {decision.target_role}")
        print(f"Reasons:            {decision.reasons}")
        print(f"Recommended Action: {decision.recommended_action}")
        print()


def _cmd_memory(args: argparse.Namespace, settings: Settings) -> None:
    """Handle the 'memory' command group."""
    from lakenterprises.memory import (
        ChatMessage,
        LongTermMemoryItem,
        MemoryType,
        MessageRole,
        RecallRequest,
        default_long_term_store,
        default_memory_service,
        default_session_store,
    )

    action = getattr(args, "memory_action", "session")

    if action == "session":
        session_id = getattr(args, "session_id", "default")
        sess = default_session_store.get_session(session_id)
        print(f"\nSession Context: {session_id}")
        print("=" * 60)
        print(f"Messages count: {len(sess.messages)}")
        for i, msg in enumerate(sess.messages, 1):
            role_val = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            print(f"  {i}. [{role_val}]: {msg.content}")
        print(f"Variables: {sess.variables}")
        print()

    elif action == "append":
        session_id = getattr(args, "session_id", "default")
        role_str = getattr(args, "role", "user") or "user"
        content = getattr(args, "content", "") or ""
        try:
            m_role = MessageRole(role_str)
        except ValueError:
            m_role = MessageRole.USER
        default_session_store.append_message(
            session_id, ChatMessage(role=m_role, content=content)
        )
        print(f"Appended message to session '{session_id}'.")

    elif action == "recall":
        session_id = getattr(args, "session_id", None)
        query = getattr(args, "query", None)
        entity_type = getattr(args, "entity_type", None)
        entity_id = getattr(args, "entity_id", None)
        res = default_memory_service.recall(
            RecallRequest(
                session_id=session_id,
                query=query,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )
        print("\nSynthesized Enterprise Memory Context:")
        print("=" * 60)
        print(res.synthesized_context)
        print()

    elif action == "store":
        entity_type = getattr(args, "entity_type", "general")
        entity_id = getattr(args, "entity_id", "0")
        key = getattr(args, "key", "note")
        content = getattr(args, "content", "")
        mem_type_str = getattr(args, "memory_type", "fact") or "fact"
        importance = float(getattr(args, "importance", 1.0) or 1.0)
        try:
            mem_type = MemoryType(mem_type_str)
        except ValueError:
            mem_type = MemoryType.FACT
        item = LongTermMemoryItem(
            entity_type=entity_type,
            entity_id=entity_id,
            memory_type=mem_type,
            key=key,
            content=content,
            importance=importance,
        )
        stored = default_long_term_store.store(item)
        print(f"Stored long-term memory ID: {stored.id}")

    elif action == "query":
        entity_type = getattr(args, "entity_type", None)
        entity_id = getattr(args, "entity_id", None)
        query = getattr(args, "query", None)
        items = default_long_term_store.query(
            entity_type=entity_type, entity_id=entity_id
        )
        print(f"\nLong-Term Memories ({len(items)} found):")
        print("=" * 60)
        for it in items:
            print(f"- [{it.entity_type}:{it.entity_id} | {it.key}]: {it.content}")
        print()


def _cmd_agents(args: argparse.Namespace, settings: Settings) -> None:
    """Handle the 'agent' command group."""
    from lakenterprises.agents import (
        BENCHMARK_SCENARIOS,
        AgentRole,
        AgentTask,
        ComplianceAgent,
        DocumentAnalysisAgent,
        EscalationHandoffAgent,
        KnowledgeRetrievalAgent,
        ResponseDraftingAgent,
        SupervisorAgent,
        evaluate_scenario,
    )

    action = getattr(args, "agent_action", "eval")

    if action == "eval":
        print("\nRunning Specialist Agent Benchmark Scenarios:")
        print("=" * 60)
        agents_map = {
            AgentRole.SUPERVISOR: SupervisorAgent(),
            AgentRole.DOCUMENT_ANALYST: DocumentAnalysisAgent(),
            AgentRole.COMPLIANCE: ComplianceAgent(),
            AgentRole.KNOWLEDGE_RETRIEVER: KnowledgeRetrievalAgent(),
            AgentRole.RESPONSE_DRAFTER: ResponseDraftingAgent(),
            AgentRole.ESCALATION_HANDOFF: EscalationHandoffAgent(),
        }
        passed_count = 0
        for scenario in BENCHMARK_SCENARIOS:
            agent = agents_map.get(scenario.target_role)
            eval_res = evaluate_scenario(agent, scenario)
            status_symbol = "✅ PASS" if eval_res["passed"] else "❌ FAIL"
            if eval_res["passed"]:
                passed_count += 1
            print(
                f"{status_symbol} | {scenario.id} | {scenario.title} "
                f"({eval_res['latency_ms']:.1f}ms)"
            )
            if not eval_res["passed"]:
                for f in eval_res.get("failures", []):
                    print(f"       - {f}")
        print(
            f"\nBenchmark Result: {passed_count}/{len(BENCHMARK_SCENARIOS)} passed.\n"
        )

    elif action == "run":
        role_str = getattr(args, "role", "supervisor") or "supervisor"
        instruction = getattr(args, "instruction", "") or ""
        agents_map = {
            "supervisor": SupervisorAgent(),
            "document_analyst": DocumentAnalysisAgent(),
            "compliance": ComplianceAgent(),
            "knowledge_retriever": KnowledgeRetrievalAgent(),
            "response_drafter": ResponseDraftingAgent(),
            "escalation_handoff": EscalationHandoffAgent(),
        }
        agent = agents_map.get(role_str)
        if not agent:
            print(f"Unknown agent role '{role_str}'", file=sys.stderr)
            sys.exit(1)
        task = AgentTask(
            role=agent.role,
            instruction=instruction,
            parameters={"amount": float(getattr(args, "amount", 0.0) or 0.0)},
        )
        res = agent.run(task)
        print(f"\nAgent Execution Result [{agent.name}]:")
        print("=" * 60)
        print(f"Status:     {res.status.value}")
        print(f"Confidence: {res.confidence_score}")
        print(f"Output:     {json.dumps(res.output_data, indent=2)}")
        print()


# ---------------------------------------------------------------------------
# Subcommand: workflow (Phase 10)
# ---------------------------------------------------------------------------


def _cmd_workflow(args: argparse.Namespace, settings: Settings) -> None:
    """Execute enterprise workflow graph or inspect tracing events."""
    import json
    import uuid

    from lakenterprises.workflow import WorkflowEngine, global_tracer

    action = getattr(args, "workflow_action", "run")
    process_id = getattr(args, "process_id", None) or f"proc-{uuid.uuid4().hex[:8]}"

    if action == "run":
        engine = WorkflowEngine()
        title = getattr(args, "title", "Enterprise Investigation Workflow")
        instruction = getattr(args, "instruction", "Standard enterprise process")
        amount = getattr(args, "amount", 5000.0)

        print(f"\nExecuting Enterprise Workflow Graph [Process: {process_id}]")
        print("=" * 65)
        print(f"Title:       {title}")
        print(f"Instruction: {instruction}")
        print(f"Amount:      ${amount:,.2f}")
        print("-" * 65)

        state = engine.run(
            process_id=process_id,
            title=title,
            instruction=instruction,
            initial_context={"amount": amount},
        )

        print("Workflow Execution Completed:")
        print(f"Status:             {state.get('current_status')}")
        print(f"Active Node:        {state.get('active_node')}")
        print(f"Human Intervention: {state.get('human_intervention_required')}")
        print(f"Confidence Score:   {state.get('confidence_score')}")
        print(f"Final Outcome:      {state.get('final_outcome')}")
        print(f"Execution Path:     {' -> '.join(state.get('routing_history', []))}")
        events = global_tracer.get_events(process_id)
        print(f"Traced Events:      {len(events)} events recorded.")
        print()

    elif action == "trace":
        events = global_tracer.get_events(process_id)
        print(f"\nTrace Events for Process [{process_id}] ({len(events)} events):")
        print("=" * 65)
        for ev in events:
            event_type_name = str(getattr(ev.event_type, "value", ev.event_type))
            print(
                f"[{ev.timestamp[:19]}] {event_type_name:18} | "
                f"Node: {ev.node_name or 'N/A':18} | Step: {ev.step_number}"
            )
            if ev.payload:
                print(f"    Payload: {json.dumps(ev.payload)}")
        print()


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

    # ── process ────────────────────────────────────────────────────────
    process_parser = subparsers.add_parser(
        "process",
        help="Enterprise process and task workflow management",
        description="Manage process templates, instances, tasks, and run lifecycle demos.",
    )
    process_parser.add_argument(
        "action",
        choices=["list", "start", "status", "run-demo"],
        help="Action to perform: list, start, status, or run-demo.",
    )
    process_parser.add_argument(
        "--template-id",
        default=None,
        help="Template ID to instantiate (for 'start').",
    )
    process_parser.add_argument(
        "--instance-id",
        default=None,
        help="Instance ID to inspect (for 'status').",
    )
    process_parser.add_argument(
        "--title",
        default=None,
        help="Instance title (for 'start').",
    )

    # ── tools ──────────────────────────────────────────────────────────
    tools_parser = subparsers.add_parser(
        "tools",
        help="Agent tools discovery, inspection, and execution",
        description="List, inspect, and execute agent enterprise integration tools.",
    )
    tools_parser.add_argument(
        "action",
        choices=["list", "inspect", "run"],
        help="Action: list registered tools, inspect a schema, or run a tool.",
    )
    tools_parser.add_argument(
        "--tool-name",
        default=None,
        help="Name of the tool to inspect or execute.",
    )
    tools_parser.add_argument(
        "--params",
        default="{}",
        help="JSON string of arguments for the tool execution.",
    )
    tools_parser.add_argument(
        "--roles",
        default="admin",
        help="Comma-separated user roles executing the tool (default: admin).",
    )
    tools_parser.add_argument(
        "--user-id",
        default="cli_user",
        help="User ID executing the tool (default: cli_user).",
    )
    tools_parser.add_argument(
        "--approval-id",
        default=None,
        help="Approval request ID if tool requires prior approval.",
    )

    # ── guardrails ─────────────────────────────────────────────────────
    guardrails_parser = subparsers.add_parser(
        "guardrails",
        help="Guardrails security evaluation, PII scrubbing, and rules",
        description="Inspect PII/secrets, check prompt injection, and evaluate escalation severity.",
    )
    guardrails_parser.add_argument(
        "action",
        choices=["scrub", "check", "evaluate"],
        help="Action: scrub PII/secrets, check prompt injection, or evaluate escalation.",
    )
    guardrails_parser.add_argument(
        "--text",
        default="",
        help="Input text for 'scrub' or 'check'.",
    )
    guardrails_parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode for 'check': raise error if injection detected.",
    )
    guardrails_parser.add_argument(
        "--event-type",
        default="INCIDENT",
        help="Event type for 'evaluate' (default: INCIDENT).",
    )
    guardrails_parser.add_argument(
        "--payload",
        default="{}",
        help="JSON payload for 'evaluate' rule testing.",
    )

    # ── memory ─────────────────────────────────────────────────────────
    memory_parser = subparsers.add_parser(
        "memory",
        help="Manage short-term and long-term enterprise memory",
        description="Inspect sessions, recall context, or manage durable memories.",
    )
    memory_parser.add_argument(
        "memory_action",
        choices=["session", "append", "recall", "store", "query"],
        help="Memory operation to execute.",
    )
    memory_parser.add_argument(
        "--session-id",
        default="default",
        help="Session identifier for conversational memory.",
    )
    memory_parser.add_argument(
        "--role",
        default="user",
        help="Message role for 'append' (user, assistant, system).",
    )
    memory_parser.add_argument(
        "--content",
        default="",
        help="Content text for message turn or memory item.",
    )
    memory_parser.add_argument(
        "--entity-type",
        default=None,
        help="Entity type for long-term memory (e.g. customer, process).",
    )
    memory_parser.add_argument(
        "--entity-id",
        default=None,
        help="Entity identifier for long-term memory (e.g. CUST-1001).",
    )
    memory_parser.add_argument(
        "--key",
        default="general",
        help="Topic key for memory item.",
    )
    memory_parser.add_argument(
        "--memory-type",
        default="fact",
        help="Memory classification (fact, preference, decision).",
    )
    memory_parser.add_argument(
        "--importance",
        type=float,
        default=1.0,
        help="Importance score (0.0 to 5.0).",
    )
    memory_parser.add_argument(
        "--query",
        default=None,
        help="Search query for memory recall or query.",
    )

    # ── agent ──────────────────────────────────────────────────────────
    agent_parser = subparsers.add_parser(
        "agent",
        help="Execute and evaluate Phase 9 specialist agents",
        description="Run individual specialist agents or run benchmark evaluations.",
    )
    agent_parser.add_argument(
        "agent_action",
        choices=["eval", "run"],
        default="eval",
        nargs="?",
        help="Action to execute ('eval' or 'run').",
    )
    agent_parser.add_argument(
        "--role",
        choices=[
            "supervisor",
            "document_analyst",
            "compliance",
            "knowledge_retriever",
            "response_drafter",
            "escalation_handoff",
        ],
        default="supervisor",
        help="Specialist agent role for 'run'.",
    )
    agent_parser.add_argument(
        "--instruction",
        default="Perform standard evaluation",
        help="Instruction prompt for specialist agent.",
    )
    agent_parser.add_argument(
        "--amount",
        type=float,
        default=0.0,
        help="Transaction amount parameter for compliance check.",
    )

    # ── workflow ───────────────────────────────────────────────────────
    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Execute and inspect Phase 10 enterprise workflow graph",
        description="Run enterprise workflow graph with checkpointer and tracing.",
    )
    workflow_parser.add_argument(
        "workflow_action",
        choices=["run", "trace"],
        default="run",
        nargs="?",
        help="Workflow action ('run' or 'trace').",
    )
    workflow_parser.add_argument(
        "--id",
        dest="process_id",
        default=None,
        help="Process ID to run or inspect.",
    )
    workflow_parser.add_argument(
        "--title",
        default="Enterprise Investigation Workflow",
        help="Title or description of the workflow execution.",
    )
    workflow_parser.add_argument(
        "--instruction",
        default="Investigate invoice dispute and verify compliance policies",
        help="Primary instruction prompt for the workflow.",
    )
    workflow_parser.add_argument(
        "--amount",
        type=float,
        default=5000.0,
        help="Transaction amount context for workflow execution.",
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

    elif command == "process":
        _cmd_process(args, settings)

    elif command == "tools":
        _cmd_tools(args, settings)

    elif command == "guardrails":
        _cmd_guardrails(args, settings)

    elif command == "memory":
        _cmd_memory(args, settings)

    elif command == "agent":
        _cmd_agents(args, settings)

    elif command == "workflow":
        _cmd_workflow(args, settings)

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

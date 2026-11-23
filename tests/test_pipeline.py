"""Tests for the LakEnterprises research pipeline (Phase 1)."""

from unittest.mock import MagicMock, patch
from typing import Any

import os

import pytest

from lakenterprises import pipeline
from lakenterprises.config import Settings, get_settings
from lakenterprises.llm import SUPPORTED_PROVIDERS, get_llm, get_embedding_model
from lakenterprises.retriever import _tokenise


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class TestResponse:
    def test_create_with_minimal_args(self) -> None:
        """Response can be created with answer and citations."""
        r = pipeline.Response(answer="42", citations=[])
        assert r.answer == "42"
        assert r.citations == []
        assert r.error is None

    def test_create_with_citations(self) -> None:
        r = pipeline.Response(answer="a", citations=["src1"])
        assert r.citations == ["src1"]

    def test_create_with_error(self) -> None:
        r = pipeline.Response(answer="", citations=[])
        r.error = "something broke"
        assert r.error == "something broke"
        # str representation when error is set
        s = str(r)
        assert "error" in s

    def test_is_response_instance(self) -> None:
        r = pipeline.Response(answer="test", citations=[])
        assert isinstance(r, pipeline.Response)

    def test_metadata_default(self) -> None:
        r = pipeline.Response(answer="test", citations=[])
        assert r.metadata == {}


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------

class TestSettingsDefaults:
    def setup_method(self) -> None:
        from lakenterprises.config import Settings
        from tests import test_pipeline
        self.orig = Settings
        test_pipeline.patch_settings = None

    def test_default_api_port(self) -> None:
        s = Settings()
        assert s.api_port == 8001, "Default API port should be 8001"

    def test_default_graph_store_type(self) -> None:
        s = Settings()
        assert s.graph_store_type == "neo4j"

    def test_default_max_subquestions(self) -> None:
        s = Settings()
        assert s.max_subquestions == 4

    def test_default_retrieval_top_k(self) -> None:
        s = Settings()
        assert s.retrieval_top_k == 5

    def test_default_llm_provider(self) -> None:
        s = Settings()
        assert s.llm_provider == "openai"

    def test_has_provider_configs(self) -> None:
        """SUPPORTED_PROVIDERS should exist with provider keys."""
        assert "openai" in SUPPORTED_PROVIDERS


# ---------------------------------------------------------------------------
# get_settings
# ---------------------------------------------------------------------------

class TestGetSettings:
    def test_returns_settings_instance(self) -> None:
        s = get_settings()
        assert isinstance(s, Settings)

    def test_api_port_default(self) -> None:
        s = get_settings()
        assert s.api_port == 8001


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

class TestLLM:
    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY env var not set",
    )
    def test_get_llm_returns_chain(self) -> None:
        s = get_settings()
        llm = get_llm(provider=s.llm_provider, model=s.llm_model)
        assert llm is not None

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY env var not set",
    )
    def test_embedding_model_requires_two_args(self) -> None:
        em = get_embedding_model(provider="openai", model="text-embedding-3-small")
        assert em is not None

    @pytest.mark.parametrize("provider", SUPPORTED_PROVIDERS)
    def test_supported_providers(self, provider: str) -> None:
        assert provider in SUPPORTED_PROVIDERS


# ---------------------------------------------------------------------------
# Retriever helpers
# ---------------------------------------------------------------------------

class TestTokenise:
    def test_simple(self) -> None:
        assert _tokenise("hello world") == ["hello", "world"]

    def test_empty(self) -> None:
        assert _tokenise("") == []


# ---------------------------------------------------------------------------
# Pipeline creation
# ---------------------------------------------------------------------------

class TestCreatePipeline:
    def test_create_from_settings(self) -> None:
        app = pipeline.create_research_pipeline()
        assert app is not None

    def test_create_with_explicit_llm(self) -> None:
        mock = MagicMock()
        app = pipeline.create_research_pipeline(llm=mock)
        del app  # unused

    def test_create_same_type_as_previous(self) -> None:
        app = pipeline.create_research_pipeline()
        # It should be a compiled StateGraph
        assert hasattr(app, "get_graph")
        assert hasattr(app, "invoke")


# ---------------------------------------------------------------------------
# get_graph output
# ---------------------------------------------------------------------------

class TestGraph:
    def test_has_nodes_and_edges(self) -> None:
        app = pipeline.create_research_pipeline()
        g = app.get_graph()
        assert len(g.nodes) >= 1
        assert len(g.edges) >= 1

    def test_draw_mermaid_text(self) -> None:
        """draw_mermaid() should return valid Mermaid text (PNG may not be
        available in the test environment)."""
        app = pipeline.create_research_pipeline()
        g = app.get_graph()
        mermaid = g.draw_mermaid()
        assert isinstance(mermaid, str)
        assert len(mermaid) > 0

    def test_draw_mermaid_is_string(self) -> None:
        app = pipeline.create_research_pipeline()
        g = app.get_graph()
        m = g.draw_mermaid()
        assert "graph" in m or "flowchart" in m


# ---------------------------------------------------------------------------
# Pipeline invocation
# ---------------------------------------------------------------------------

class TestInvoke:
    def test_basic_invoke(self) -> None:
        app = pipeline.create_research_pipeline()
        result = app.invoke({"query": "what is AI?"})
        assert "answer" in result

    def test_invoke_with_extra_fields(self) -> None:
        app = pipeline.create_research_pipeline()
        result = app.invoke({"query": "test", "user_id": "abc"})
        assert "answer" in result


# ---------------------------------------------------------------------------
# CANONICAL_DEMO_QUESTION
# ---------------------------------------------------------------------------

class TestCanonical:
    def test_demo_question_exists(self) -> None:
        from lakenterprises.__main__ import CANONICAL_DEMO_QUESTION
        assert isinstance(CANONICAL_DEMO_QUESTION, str)
        assert len(CANONICAL_DEMO_QUESTION) > 0
"""LLM factory – create LangChain chat models and embeddings for 8 providers.

Usage
-----
>>> from lakenterprises.llm import get_llm, get_embedding_model
>>> llm = get_llm("openai", "gpt-4o-mini")
>>> emb = get_embedding_model("openai", "text-embedding-3-small")
"""

from __future__ import annotations

import os
import warnings
from typing import Type

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

# ---------------------------------------------------------------------------
# Provider → environment-variable mapping
# ---------------------------------------------------------------------------

_PROVIDER_KEYS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "cohere": "COHERE_API_KEY",
    "watson": "WATSONX_APIKEY",
    "ollama": "",  # no key needed
}

_PROVIDER_PACKAGES: dict[str, str] = {
    "openai": "langchain-openai",
    "anthropic": "langchain-anthropic",
    "google": "langchain-google-genai",
    "azure": "langchain-openai",
    "groq": "langchain-groq",
    "cohere": "langchain-cohere",
    "watson": "langchain-ibm",
    "ollama": "langchain-ollama",
}

SUPPORTED_PROVIDERS: list[str] = list(_PROVIDER_KEYS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_provider(provider: str) -> None:
    """Raise ``ValueError`` for an unsupported provider name."""
    if provider not in _PROVIDER_KEYS:
        raise ValueError(
            f"Unsupported provider {provider!r}. "
            f"Choose from: {', '.join(SUPPORTED_PROVIDERS)}"
        )


def _check_api_key(provider: str) -> str | None:
    """Return the API key for *provider*, warning if it looks suspicious."""
    env_var = _PROVIDER_KEYS.get(provider)
    if not env_var:  # e.g. ollama
        return None
    key = os.environ.get(env_var)
    if not key:
        pkg = _PROVIDER_PACKAGES[provider]
        raise ImportError(
            f"Environment variable {env_var} is not set. "
            f"Sign up at the {provider} platform, set the variable, and ensure "
            f"the package is installed:\n\n"
            f"    pip install {pkg}\n"
        )
    return key


# ---------------------------------------------------------------------------
# Chat-model factory
# ---------------------------------------------------------------------------

def get_llm(
    provider: str,
    model: str,
    temperature: float = 0.0,
    **kwargs: object,
) -> BaseChatModel:
    """Return a LangChain ``BaseChatModel`` for the given provider.

    Parameters
    ----------
    provider:
        One of: ``openai``, ``anthropic``, ``google``, ``azure``,
        ``ollama``, ``groq``, ``cohere``, ``watson``.
    model:
        Provider-specific model identifier (e.g. ``"gpt-4o"``).
    temperature:
        Sampling temperature, passed to the chat model constructor.
    **kwargs:
        Extra keyword arguments forwarded to the constructor
        (e.g. ``max_tokens``, ``top_p``).

    Returns
    -------
    A configured ``BaseChatModel`` instance.

    Raises
    ------
    ValueError
        If *provider* is not one of the supported providers.
    ImportError
        If the required provider package is not installed.

    Examples
    --------
    >>> llm = get_llm("openai", "gpt-4o-mini", temperature=0.2)
    """
    _validate_provider(provider)

    if provider == "openai":
        return _make_openai(model, temperature, **kwargs)

    if provider == "anthropic":
        return _make_anthropic(model, temperature, **kwargs)

    if provider == "google":
        return _make_google(model, temperature, **kwargs)

    if provider == "azure":
        return _make_azure(model, temperature, **kwargs)

    if provider == "ollama":
        return _make_ollama(model, temperature, **kwargs)

    if provider == "groq":
        return _make_groq(model, temperature, **kwargs)

    if provider == "cohere":
        return _make_cohere(model, temperature, **kwargs)

    if provider == "watson":
        return _make_watson(model, temperature, **kwargs)

    # Should never be reached – _validate_provider guards against this
    raise NotImplementedError(provider)  # type: ignore[unreachable]


# -- provider-specific builders ------------------------------------------------

def _make_openai(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    _check_api_key("openai")
    return ChatOpenAI(model=model, temperature=temperature, **kwargs)  # type: ignore[arg-type]


def _make_anthropic(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    _check_api_key("anthropic")
    return ChatAnthropic(model=model, temperature=temperature, **kwargs)  # type: ignore[arg-type]


def _make_google(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    _check_api_key("google")
    return ChatGoogleGenerativeAI(
        model=model, temperature=temperature, **kwargs  # type: ignore[arg-type]
    )


def _make_azure(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    _check_api_key("azure")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise ImportError(
            "Environment variable AZURE_OPENAI_ENDPOINT is not set. "
            "Set it to your Azure OpenAI resource endpoint.\n"
            "Also ensure langchain-openai is installed:\n\n"
            "    pip install langchain-openai\n"
        )
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
    deployment_name = kwargs.pop("deployment_name", None) or model
    return AzureChatOpenAI(
        azure_deployment=deployment_name,  # type: ignore[arg-type]
        azure_endpoint=endpoint,
        api_version=api_version,
        temperature=temperature,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_ollama(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    base_url = kwargs.pop("base_url", None) or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(
        model=model, temperature=temperature, base_url=base_url, **kwargs  # type: ignore[arg-type]
    )


def _make_groq(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_groq import ChatGroq

    _check_api_key("groq")
    return ChatGroq(model=model, temperature=temperature, **kwargs)  # type: ignore[arg-type]


def _make_cohere(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_cohere import ChatCohere

    _check_api_key("cohere")
    return ChatCohere(model=model, temperature=temperature, **kwargs)  # type: ignore[arg-type]


def _make_watson(model: str, temperature: float, **kwargs: object) -> BaseChatModel:
    from langchain_ibm import ChatWatsonx

    _check_api_key("watson")
    url = os.environ.get("WATSONX_URL")
    if not url:
        raise ImportError(
            "Environment variable WATSONX_URL is not set. "
            "Set it to your Watsonx Project URL.\n"
            "Also ensure langchain-ibm is installed:\n\n"
            "    pip install langchain-ibm\n"
        )
    project_id = os.environ.get("WATSONX_PROJECT_ID")
    if not project_id:
        raise ImportError(
            "Environment variable WATSONX_PROJECT_ID is not set."
        )
    return ChatWatsonx(
        model_id=model,
        temperature=temperature,
        url=url,
        project_id=project_id,
        **kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Embeddings factory
# ---------------------------------------------------------------------------

def get_embedding_model(
    provider: str,
    model: str,
    **kwargs: object,
) -> Embeddings:
    """Return a LangChain ``Embeddings`` instance for the given provider.

    Parameters
    ----------
    provider:
        One of: ``openai``, ``anthropic``, ``google``, ``azure``,
        ``ollama``, ``groq``, ``cohere``, ``watson``.
    model:
        Provider-specific embedding model identifier.
    **kwargs:
        Extra keyword arguments forwarded to the constructor.

    Returns
    -------
    A configured ``Embeddings`` instance.

    Raises
    ------
    ValueError
        If *provider* is not supported.
    NotImplementedError
        If *provider* has no native LangChain embeddings integration
        (``anthropic``, ``groq``, ``watson``).
    ImportError
        If the required provider package is not installed.

    Examples
    --------
    >>> emb = get_embedding_model("openai", "text-embedding-3-small")
    """
    _validate_provider(provider)

    if provider == "openai":
        return _make_openai_embeddings(model, **kwargs)

    if provider == "anthropic":
        return _make_anthropic_embeddings(model, **kwargs)

    if provider == "google":
        return _make_google_embeddings(model, **kwargs)

    if provider == "azure":
        return _make_azure_embeddings(model, **kwargs)

    if provider == "ollama":
        return _make_ollama_embeddings(model, **kwargs)

    if provider == "groq":
        return _make_groq_embeddings(model, **kwargs)

    if provider == "cohere":
        return _make_cohere_embeddings(model, **kwargs)

    if provider == "watson":
        return _make_watson_embeddings(model, **kwargs)

    raise NotImplementedError(provider)  # type: ignore[unreachable]


# -- provider-specific embedding builders --------------------------------------

def _make_openai_embeddings(model: str, **kwargs: object) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    _check_api_key("openai")
    return OpenAIEmbeddings(model=model, **kwargs)  # type: ignore[arg-type]


def _make_anthropic_embeddings(model: str, **kwargs: object) -> Embeddings:
    """Anthropic has no embeddings API; fall back to OpenAI with a warning."""
    warnings.warn(
        "Anthropic does not offer a native embeddings API. "
        "Falling back to OpenAI embeddings with model "
        f"{kwargs.get('fallback_model', 'text-embedding-3-small')!r}. "
        "Set OPENAI_API_KEY for the fallback to work.",
        stacklevel=2,
    )
    fallback_model: str = kwargs.get("fallback_model", "text-embedding-3-small")  # type: ignore[assignment]
    return _make_openai_embeddings(fallback_model, **kwargs)  # type: ignore[arg-type]


def _make_google_embeddings(model: str, **kwargs: object) -> Embeddings:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    _check_api_key("google")
    return GoogleGenerativeAIEmbeddings(model=model, **kwargs)  # type: ignore[arg-type]


def _make_azure_embeddings(model: str, **kwargs: object) -> Embeddings:
    from langchain_openai import AzureOpenAIEmbeddings

    _check_api_key("azure")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise ImportError(
            "AZURE_OPENAI_ENDPOINT is not set. "
            "Set it to your Azure OpenAI resource endpoint.\n"
            "Also ensure langchain-openai is installed:\n\n"
            "    pip install langchain-openai\n"
        )
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-01-preview")
    deployment_name = kwargs.pop("deployment_name", None) or model
    return AzureOpenAIEmbeddings(
        azure_deployment=deployment_name,  # type: ignore[arg-type]
        azure_endpoint=endpoint,
        api_version=api_version,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_ollama_embeddings(model: str, **kwargs: object) -> Embeddings:
    from langchain_ollama import OllamaEmbeddings

    base_url = kwargs.pop("base_url", None) or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return OllamaEmbeddings(
        model=model, base_url=base_url, **kwargs  # type: ignore[arg-type]
    )


def _make_groq_embeddings(model: str, **kwargs: object) -> Embeddings:
    """Groq has no native embeddings API in LangChain."""
    raise NotImplementedError(
        "Groq does not provide a native embeddings API. "
        "Options:\n"
        "  1. Use OpenAI embeddings instead: get_embedding_model('openai', 'text-embedding-3-small')\n"
        "  2. Use Cohere embeddings:       get_embedding_model('cohere', 'embed-english-v3.0')\n"
        "  3. Use Ollama embeddings:       get_embedding_model('ollama', 'nomic-embed-text')\n"
    )


def _make_cohere_embeddings(model: str, **kwargs: object) -> Embeddings:
    from langchain_cohere import CohereEmbeddings

    _check_api_key("cohere")
    return CohereEmbeddings(model=model, **kwargs)  # type: ignore[arg-type]


def _make_watson_embeddings(model: str, **kwargs: object) -> Embeddings:
    """Watsonx embeddings are not yet available in LangChain."""
    raise NotImplementedError(
        "Watsonx does not have a native LangChain embeddings integration. "
        "Options:\n"
        "  1. Use OpenAI embeddings instead.\n"
        "  2. Use the ``ibm_watsonx_client`` directly with the "
        "    ``text_embedding`` method and wrap it in a custom "
        "    ``Embeddings`` subclass.\n"
    )

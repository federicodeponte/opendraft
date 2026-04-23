"""
Token Counting Utility
Accurately count tokens for different LLM providers
"""

import logging
import re
logger = logging.getLogger(__name__)


def _default_model_name() -> str:
    """Return a reasonable default model for the active provider."""
    import os

    provider = (os.getenv('AI_PROVIDER', 'gemini').strip().lower())
    if provider in {'codex', 'openai-codex', 'openai'}:
        return os.getenv('OPENAI_MODEL', 'gpt-4.1-nano')
    return os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview')


def count_tokens(text: str, model_name: str | None = None) -> int:
    """
    Count tokens in text using the appropriate method for the model.

    For Gemini models: Uses Gemini's native token counter
    For OpenAI models: Uses approximation (1 token ≈ 4 characters)

    Args:
        text: Text to count tokens for
        model_name: Name of the model

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0

    model_name = model_name or _default_model_name()

    # Try Gemini token counter first
    if "gemini" in model_name.lower():
        return _count_gemini_tokens(text, model_name)
    elif "gpt" in model_name.lower() or "openai" in model_name.lower():
        return _count_openai_tokens(text)
    else:
        # Fallback to character-based approximation
        return _count_fallback_tokens(text)


def count_prompt_tokens(prompt: str, model_name: str | None = None) -> int:
    """
    Count tokens specifically for a prompt.

    Args:
        prompt: Prompt text
        model_name: Name of the model

    Returns:
        Number of tokens
    """
    return count_tokens(prompt, model_name)


def count_response_tokens(response: str, model_name: str | None = None) -> int:
    """
    Count tokens specifically for a response.

    Args:
        response: Response text
        model_name: Name of the model

    Returns:
        Number of tokens
    """
    return count_tokens(response, model_name)


def _count_gemini_tokens(text: str, model_name: str) -> int:
    """
    Count tokens using Gemini's token counter.

    Args:
        text: Text to count
        model_name: Gemini model name

    Returns:
        Token count
    """
    try:
        import os
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return _count_fallback_tokens(text)

        client = genai.Client(api_key=api_key)

        # Count tokens using new API
        response = client.models.count_tokens(model=model_name, contents=text)
        token_count = response.total_tokens

        logger.debug(f"Gemini token count for {len(text)} chars: {token_count} tokens")
        return token_count

    except Exception as e:
        logger.warning(
            f"Failed to count tokens with Gemini ({type(e).__name__}): {str(e)}, "
            f"falling back to approximation"
        )
        # Fallback to approximation
        return _count_fallback_tokens(text)


def _count_openai_tokens(text: str) -> int:
    """
    Count tokens for OpenAI models.

    OpenAI token counting can be more accurate with tiktoken library,
    but we provide a reasonable approximation.

    Args:
        text: Text to count

    Returns:
        Estimated token count
    """
    try:
        import tiktoken

        # Try to use tiktoken for more accurate counting
        enc = tiktoken.encoding_for_model("gpt-4")
        tokens = enc.encode(text)
        token_count = len(tokens)

        logger.debug(f"OpenAI token count for {len(text)} chars: {token_count} tokens")
        return token_count

    except ImportError:
        logger.debug("tiktoken not available, using approximation for OpenAI tokens")
        return _count_fallback_tokens(text)
    except Exception as e:
        logger.warning(
            f"Failed to count OpenAI tokens ({type(e).__name__}): {str(e)}, "
            f"using approximation"
        )
        return _count_fallback_tokens(text)


def _count_fallback_tokens(text: str) -> int:
    """
    Fallback token counter using character-based approximation.

    Approximation: 1 token ≈ 4 characters (rough average)
    This is a conservative estimate.

    Args:
        text: Text to count

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Remove extra whitespace
    cleaned = re.sub(r"\s+", " ", text.strip())

    # Rough approximation: 1 token per 4 characters
    # This is conservative and may underestimate
    token_count = max(1, len(cleaned) // 4)

    logger.debug(f"Fallback token count for {len(cleaned)} chars: {token_count} tokens")
    return token_count


def estimate_tokens_in_messages(
    messages: list, model_name: str | None = None
) -> int:
    """
    Estimate total tokens in a list of messages.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Name of the model

    Returns:
        Total estimated token count
    """
    total_tokens = 0

    for message in messages:
        content = message.get("content", "")
        role = message.get("role", "")

        # Add tokens for content
        total_tokens += count_tokens(content, model_name)

        # Add overhead for role markers (usually ~4-5 tokens per message)
        total_tokens += 5

    # Add general conversation overhead
    total_tokens += 10

    return total_tokens


if __name__ == "__main__":
    # Test token counting
    test_text = "This is a test string to count tokens for different models."

    print(f"Text: {test_text}")
    print(f"Character count: {len(test_text)}")
    print(f"Fallback token estimate: {_count_fallback_tokens(test_text)}")

    # Test with Gemini
    try:
        gemini_count = count_tokens(test_text, "gemini-2.0-flash")
        print(f"Gemini token count: {gemini_count}")
    except Exception as e:
        print(f"Gemini counting failed: {e}")

    # Test with OpenAI
    try:
        openai_count = count_tokens(test_text, "gpt-4")
        print(f"OpenAI token count: {openai_count}")
    except Exception as e:
        print(f"OpenAI counting failed: {e}")

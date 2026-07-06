#!/usr/bin/env python3
"""
ABOUTME: Production agent utilities for draft generation
ABOUTME: Core functions for model setup, agent execution, and citation research

Extracted from tests/test_utils.py for proper production use.
These are the essential utilities needed by draft_generator.py and modal_worker.py.
"""

import sys
import time
import logging
import os
import json
from pathlib import Path
from typing import Optional, Callable, Tuple, List, TYPE_CHECKING, Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

# Safe print function that handles broken pipes and respects CLI quiet mode
def safe_print(*args, **kwargs):
    """Print wrapper that catches BrokenPipeError and respects CLI quiet mode."""
    # Check verbosity setting from orchestrator (CLI quiet mode)
    try:
        from utils.api_citations.orchestrator import _verbose_research
        if not _verbose_research:
            return  # Suppress in CLI quiet mode
    except ImportError:
        pass  # If orchestrator not available, continue normally

    try:
        print(*args, **kwargs)
    except (BrokenPipeError, OSError):
        # Pipe is closed (worker running with stdio: 'ignore'), use logger instead
        message = ' '.join(str(arg) for arg in args)
        logger.debug(message)
        # Prevent further broken pipe errors by redirecting stdout
        try:
            sys.stdout = open(os.devnull, 'w')
        except:
            pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from config import get_config
from concurrency.concurrency_config import get_concurrency_config
from utils.output_validators import ValidationResult
from utils.api_citations.orchestrator import CitationResearcher
from utils.citation_database import Citation
from utils.gemini_client import GeminiModelWrapper
from utils.deep_research import DeepResearchPlanner
from utils.token_tracker import CallStatus

# Configure logging
logger = logging.getLogger(__name__)


def setup_model(model_override: Optional[str] = None) -> Any:
    """
    Initialize and return configured Gemini model wrapper.

    Args:
        model_override: Optional model name to override config default

    Returns:
        GeminiModelWrapper: Configured model wrapper with generate_content() method

    Raises:
        ValueError: If API key is missing or model name is invalid
    """
    config = get_config()

    if not config.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found. Set it in .env file or environment variables."
        )

    client = genai.Client(api_key=config.google_api_key)
    model_name = model_override or config.model.model_name

    return GeminiModelWrapper(
        client=client,
        model_name=model_name,
        temperature=config.model.temperature,
    )


def load_prompt(prompt_path: str) -> str:
    """
    Load agent prompt from markdown file.

    Args:
        prompt_path: Path to prompt file (relative to project root or absolute)

    Returns:
        str: Content of the prompt file

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    config = get_config()
    path = Path(prompt_path)

    # If relative path, try relative to project root
    if not path.is_absolute():
        path = config.paths.project_root / path

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def run_agent(
    model: Any,
    name: str,
    prompt_path: str,
    user_input: str,
    save_to: Optional[Path] = None,
    verbose: bool = True,
    validators: Optional[List[Callable[[str], ValidationResult]]] = None,
    max_retries: int = 3,
    skip_validation: bool = False,
    token_tracker: Optional[Any] = None,
    token_stage: Optional[str] = None,
) -> str:
    """
    Run an AI agent with given prompt and input, with optional validation.

    This function is the core execution layer for all agents in the draft pipeline.
    It handles LLM interaction, output validation, retries, and file I/O.

    Args:
        model: Configured Gemini model instance
        name: Human-readable name for the agent (for logging)
        prompt_path: Path to agent prompt file
        user_input: User's request/input for the agent
        save_to: Optional path to save output
        verbose: Whether to print progress messages
        validators: Optional list of validation functions to apply to output
        max_retries: Maximum retry attempts if validation fails (default: 3)
        skip_validation: If True, skip all validation checks (for automated runs)

    Returns:
        str: Validated agent output text

    Raises:
        Exception: If agent execution fails or validation fails after all retries
    """
    # Override validators if skip_validation is True
    if skip_validation:
        validators = None
        logger.info(f"Agent '{name}': Validation skipped (skip_validation=True)")
    if verbose:
        safe_print(f"\n{'='*70}")
        safe_print(f"🤖 {name}")
        safe_print(f"{'='*70}")

    # Load agent prompt
    agent_prompt = load_prompt(prompt_path)

    # Combine agent prompt with user input
    full_prompt = f"{agent_prompt}\n\n---\n\nUser Request:\n{user_input}"

    logger.debug(f"Agent '{name}': Starting execution")
    logger.debug(f"Prompt length: {len(full_prompt)} chars")
    logger.debug(f"Validators: {len(validators) if validators else 0}")

    # Initialize output variable with explicit type
    output: str = ""

    # Empty loop detection (V3 feature): exit early if model produces empty output repeatedly
    consecutive_empty_outputs = 0
    MAX_CONSECUTIVE_EMPTY = 3

    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        if verbose and attempt > 0:
            safe_print(f"Retry attempt {attempt}/{max_retries}...", end=' ', flush=True)
        elif verbose:
            safe_print("Generating...", end=' ', flush=True)

        start_time = time.time()

        try:
            # Generate LLM response
            # Note: If Gemini tools (Google Search/URL context) hit rate limits,
            # we catch the exception and use fallbacks (DataForSEO/OpenPull)
            try:
                response = model.generate_content(full_prompt)
            except Exception as tool_error:
                error_str = str(tool_error)
                # Check if it's a rate limit error (429) from Gemini tools
                if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                    logger.warning(f"Agent '{name}': Gemini tools rate limited - will retry without tools")
                    # Retry without tools (fallback to direct generation)
                    # Note: For web search/URL context, we'd need to manually call fallbacks
                    # This is a simplified retry - full fallback integration would require
                    # detecting which tool failed and calling appropriate fallback
                    response = model.generate_content(full_prompt)
                else:
                    raise  # Re-raise if not a rate limit error
            
            # Handle function calls and other edge cases
            # Check if response has candidates
            if not response.candidates:
                raise ValueError(f"Agent '{name}': No candidates in response (likely blocked)")
            
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            # Check what parts exist in the response BEFORE accessing response.text
            # This prevents ValueError when response has function calls or no text parts
            has_text_part = False
            has_function_call = False
            
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        has_text_part = True
                        break
                    if hasattr(part, 'function_call'):
                        has_function_call = True
            
            # If no text part exists, try to extract from parts directly
            output = None
            
            if has_text_part:
                # Safe to use response.text when text part exists
                try:
                    output = str(response.text)
                except ValueError:
                    # Fallback: extract from parts
                    if hasattr(candidate, 'content') and candidate.content:
                        text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                        if text_parts:
                            output = ''.join(text_parts)
            elif has_function_call:
                # Function call detected but no text - this is an error
                raise ValueError(
                    f"Agent '{name}': Response contains function call but no text content. "
                    f"Finish reason: {finish_reason}. "
                    f"This may indicate the model attempted to call a function incorrectly. "
                    f"Try regenerating or check if tools are properly configured."
                )
            else:
                # No text part and no function call - check finish_reason
                if finish_reason == 1:  # STOP (normal) but no text - unusual
                    raise ValueError(
                        f"Agent '{name}': Response has finish_reason=1 (STOP) but no text parts. "
                        f"This may indicate an empty response or safety filter block."
                    )
                elif finish_reason == 10:  # FUNCTION_CALL
                    raise ValueError(
                        f"Agent '{name}': Response has finish_reason=10 (FUNCTION_CALL) but no text content. "
                        f"This indicates an invalid function call attempt."
                    )
                else:
                    raise ValueError(
                        f"Agent '{name}': No text content in response. "
                        f"Finish reason: {finish_reason}. "
                        f"Response may be blocked or empty."
                    )
            
            if not output:
                raise ValueError(f"Agent '{name}': Unable to extract text from response")
            
            output = str(output)

            # Defense-in-depth: scrub planning preambles, metadata, and cite_MISSING markers
            from utils.text_utils import clean_agent_output
            output = clean_agent_output(output)

            # Empty loop detection (V3 feature): track consecutive empty/trivial outputs
            if len(output.strip()) < 50:  # Effectively empty or trivial
                consecutive_empty_outputs += 1
                logger.warning(
                    f"Agent '{name}': Empty/trivial output detected ({consecutive_empty_outputs}/{MAX_CONSECUTIVE_EMPTY})"
                )
                if consecutive_empty_outputs >= MAX_CONSECUTIVE_EMPTY:
                    logger.error(
                        f"Agent '{name}': Exiting early after {MAX_CONSECUTIVE_EMPTY} consecutive empty outputs"
                    )
                    if verbose:
                        safe_print(f"⚠️ Model stuck - {MAX_CONSECUTIVE_EMPTY} consecutive empty outputs")
                    # Return whatever partial output we have (could be empty)
                    break
                # Continue to retry
                if attempt < max_retries - 1:
                    backoff_seconds = 2 ** attempt
                    time.sleep(backoff_seconds)
                    continue
            else:
                # Reset counter on successful non-empty output
                consecutive_empty_outputs = 0

            logger.debug(f"Agent '{name}': Generated {len(output)} chars in {time.time() - start_time:.1f}s")

            # Track token usage if tracker is provided
            if token_tracker and hasattr(response, 'usage_metadata'):
                try:
                    meta = response.usage_metadata
                    token_tracker.add_call(
                        stage=token_stage or name,
                        input_tokens=getattr(meta, 'prompt_token_count', 0) or 0,
                        output_tokens=getattr(meta, 'candidates_token_count', 0) or 0,
                    )
                except Exception:
                    pass  # Never break generation for tracking failures

            # Validate output if validators provided (and not skipped)
            if validators and not skip_validation:
                validation_passed = True
                for i, validator in enumerate(validators):
                    logger.debug(f"Agent '{name}': Running validator {i+1}/{len(validators)}")
                    result = validator(output)

                    if not result.is_valid:
                        validation_passed = False
                        logger.warning(
                            f"Agent '{name}': Validation failed on attempt {attempt+1}/{max_retries}: "
                            f"{result.error_message}"
                        )

                        if verbose:
                            safe_print(f"⚠️ Validation failed: {result.error_message}")

                        # If not last attempt, retry with backoff
                        if attempt < max_retries - 1:
                            backoff_seconds = 2 ** attempt  # Exponential: 1s, 2s, 4s
                            logger.debug(f"Agent '{name}': Backing off for {backoff_seconds}s")
                            time.sleep(backoff_seconds)
                            break  # Break validator loop to retry LLM call
                        else:
                            # Last attempt failed - raise error
                            error_msg = (
                                f"Agent '{name}' validation failed after {max_retries} attempts: "
                                f"{result.error_message}"
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    else:
                        logger.debug(f"Agent '{name}': Validator {i+1} passed")

                # If all validators passed, break retry loop
                if validation_passed:
                    logger.info(f"Agent '{name}': All {len(validators)} validators passed")
                    break
            else:
                # No validators - success on first attempt
                logger.debug(f"Agent '{name}': No validators, accepting output")
                break

        except Exception as e:
            if verbose:
                safe_print(f"❌ Error")

            logger.error(f"Agent '{name}': Exception on attempt {attempt+1}: {str(e)}")

            # Track failed call if tracker is provided
            if token_tracker:
                try:
                    token_tracker.add_call(
                        stage=token_stage or name,
                        input_tokens=0,
                        output_tokens=0,
                        status=CallStatus.FAILURE,
                        error_message=str(e),
                    )
                except Exception:
                    pass  # Never break generation for tracking failures

            # If not last attempt and it's a transient error, retry
            if attempt < max_retries - 1 and _is_transient_error(e):
                backoff_seconds = 2 ** attempt
                logger.debug(f"Agent '{name}': Transient error, retrying after {backoff_seconds}s")
                time.sleep(backoff_seconds)
                continue
            else:
                # Partial output capture (V3 feature): on timeout, check for any files written
                if save_to and ('timeout' in str(e).lower() or 'timed out' in str(e).lower()):
                    partial_output = _capture_partial_output(save_to, name)
                    if partial_output:
                        logger.warning(
                            f"Agent '{name}': Timeout, but captured partial output ({len(partial_output)} chars)"
                        )
                        if verbose:
                            safe_print(f"⚠️ Timeout - captured {len(partial_output)} chars of partial output")
                        output = partial_output
                        break  # Exit retry loop with partial output
                raise Exception(f"Agent '{name}' execution failed: {str(e)}") from e

    elapsed = time.time() - start_time

    # Save output if path provided
    if save_to:
        try:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with open(save_to, 'w', encoding='utf-8') as f:
                f.write(output)

            # Verify file was created successfully
            if not save_to.exists():
                raise IOError(f"Output file not created: {save_to}")

            file_size = save_to.stat().st_size
            if file_size == 0:
                raise IOError(f"Output file is empty: {save_to}")

            logger.info(f"Agent '{name}': Saved output to {save_to} ({file_size} bytes)")

        except Exception as e:
            logger.error(f"Agent '{name}': Failed to save output to {save_to}: {str(e)}")
            raise

    if verbose:
        safe_print(f"✅ Done ({elapsed:.1f}s, {len(output):,} chars)")
        if save_to:
            safe_print(f"Saved to: {save_to}")

    return output


def _capture_partial_output(save_path: Path, agent_name: str) -> Optional[str]:
    """
    Capture partial output on timeout (V3 feature).

    When an agent times out, check if any partial work was written to the output
    directory. This recovers work that would otherwise be lost.

    Args:
        save_path: Path where output would be saved
        agent_name: Name of the agent (for logging)

    Returns:
        str or None: Partial output if found, None otherwise
    """
    try:
        output_dir = save_path.parent
        if not output_dir.exists():
            return None

        # Check for the output file itself (might have been partially written)
        if save_path.exists() and save_path.stat().st_size > 0:
            content = save_path.read_text(encoding='utf-8')
            if len(content.strip()) > 50:  # Non-trivial content
                logger.info(f"Agent '{agent_name}': Found partial output in {save_path}")
                return content

        # Check for any recent files in the output directory
        recent_files = []
        for f in output_dir.iterdir():
            if f.is_file() and f.suffix in ['.md', '.txt', '.json']:
                recent_files.append((f, f.stat().st_mtime))

        if not recent_files:
            return None

        # Get most recently modified file
        recent_files.sort(key=lambda x: x[1], reverse=True)
        most_recent = recent_files[0][0]

        if most_recent.stat().st_size > 0:
            content = most_recent.read_text(encoding='utf-8')
            if len(content.strip()) > 50:
                logger.info(f"Agent '{agent_name}': Found partial output in {most_recent}")
                return content

        return None
    except Exception as e:
        logger.debug(f"Agent '{agent_name}': Partial output capture failed: {e}")
        return None


def _is_transient_error(error: Exception) -> bool:
    """
    Check if error is transient and worth retrying.
    Also signals backpressure system for rate limit errors.

    Args:
        error: Exception to check

    Returns:
        bool: True if error is transient (network, rate limit, etc.)
    """
    error_str = str(error).lower()
    # Expanded patterns from V3 - covers more network/API edge cases
    transient_patterns = [
        # Rate limiting
        'timeout',
        'rate limit',
        'rate_limit',
        'ratelimit',
        'quota',
        'throttl',
        '429',  # Too Many Requests
        # Server errors
        'service unavailable',
        'temporarily unavailable',
        'server error',
        'internal error',
        '500',  # Internal Server Error
        '502',  # Bad Gateway
        '503',  # Service Unavailable
        '504',  # Gateway Timeout
        # Network errors
        'connection reset',
        'connection refused',
        'connection closed',
        'closed connection',          # "peer closed connection ..." (httpx wording)
        'peer closed',
        'incomplete chunked read',    # truncated streaming response
        'chunked read',
        'connection error',
        'connection aborted',
        'remote end closed',
        'server disconnected',
        'broken pipe',
        'network unreachable',
        'dns',
        'ssl',
        'certificate',
        'handshake',
        # API-specific
        'resource exhausted',
        'overloaded',
        'capacity',
        'retry',
        'try again',
        'temporary',
    ]

    is_transient = any(pattern in error_str for pattern in transient_patterns)
    
    # Signal backpressure for rate limit errors
    if is_transient and ('429' in error_str or 'rate limit' in error_str or 'quota' in error_str):
        try:
            from utils.backpressure import BackpressureManager, APIType
            bp = BackpressureManager()
            bp.signal_429(APIType.GEMINI_PRIMARY)
            logger.debug("Signaled backpressure for rate limit error")
        except Exception:
            pass  # Don't fail on backpressure errors
    
    return is_transient


def rate_limit_delay(seconds: Optional[float] = None) -> None:
    """
    Sleep for rate limiting with tier-adaptive delays.

    Automatically adjusts delay based on detected API tier:
    - Free tier (10 RPM): 7 seconds (safe for 1 req/6s limit)
    - Paid tier (2,000 RPM): 0.3 seconds (safe for high throughput)

    Args:
        seconds: Manual override (default: None = use tier-adaptive delay)
    """
    if seconds is None:
        # Use tier-adaptive delay
        config = get_concurrency_config(verbose=False)
        seconds = config.rate_limit_delay

    time.sleep(seconds)


def research_citations_via_api(
    model: Any,
    research_topics: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
    target_minimum: int = 50,
    verbose: bool = True,
    # Deep Research Mode parameters
    use_deep_research: bool = False,
    topic: Optional[str] = None,
    scope: Optional[str] = None,
    seed_references: Optional[List[str]] = None,
    min_sources_deep: int = 100,
    # Timeout control
    per_topic_timeout_seconds: int = 90,  # Increased from 30s - citations need time to search multiple APIs
    # Progress reporting
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Research citations using API-backed fallback chain with optional deep research mode.

    Two modes of operation:
    1. **Standard Mode** (use_deep_research=False):
       - Uses manually provided research_topics list
       - Executes each topic through API fallback chain
       - Best for targeted, curated research queries

    2. **Deep Research Mode** (use_deep_research=True):
       - Uses DeepResearchPlanner for autonomous research strategy
       - Creates 50+ systematic queries from topic + scope + seed references
       - Best for comprehensive literature reviews (dissertations, draft)

    API Fallback Chain:
    Crossref → Semantic Scholar → Gemini Grounded → Gemini LLM (95%+ success rate)

    Args:
        model: Configured Gemini model instance (used for planning and LLM fallback)
        research_topics: List of research topics (required if use_deep_research=False)
        output_path: Path to save Scout-compatible markdown output (required if provided)
        target_minimum: Minimum citations required to pass quality gate (default: 50)
        verbose: Whether to print progress messages (default: True)

        use_deep_research: Enable deep research mode (default: False)
        topic: Main research topic (required if use_deep_research=True)
        scope: Optional research scope constraints (e.g., "EU focus; B2C and B2B")
        seed_references: Optional seed papers to expand from
        min_sources_deep: Minimum sources for deep research (default: 100)
        per_topic_timeout_seconds: Maximum time to spend on each research topic (default: 90)
        progress_callback: Optional callback(message, event_type) for progress reporting

    Returns:
        Dict with keys:
            - citations: List[Citation] - Valid citations found
            - count: int - Number of valid citations
            - sources: Dict[str, int] - Breakdown by source (Crossref, Semantic Scholar, etc.)
            - failed_topics: List[str] - Topics that failed to find citations
            - research_plan: Optional[Dict] - Deep research plan (if deep mode enabled)

    Raises:
        ValueError: If citation count < target_minimum (quality gate failure)
        ValueError: If invalid mode parameters (missing required args)
    """
    # Validate mode parameters
    if use_deep_research:
        if not topic:
            raise ValueError("Deep research mode requires 'topic' parameter")
        mode_name = "DEEP RESEARCH MODE"
    else:
        if not research_topics:
            raise ValueError("Standard mode requires 'research_topics' parameter")
        mode_name = "STANDARD MODE"

    if verbose:
        safe_print("\n" + "=" * 80)
        safe_print(f"🔬 API-BACKED SCOUT - {mode_name}")
        safe_print("=" * 80)

    # Deep Research Mode: Autonomous research planning
    research_plan: Optional[Dict[str, Any]] = None

    if use_deep_research:
        if verbose:
            safe_print(f"\n🧠 Deep Research Planning Phase")
            safe_print(f"{'='*80}")
            safe_print(f"\n📋 Input:")
            safe_print(f"   Topic: {topic}")
            if scope:
                safe_print(f"   Scope: {scope}")
            if seed_references:
                safe_print(f"   Seed References: {len(seed_references)}")
            safe_print(f"   Target: {min_sources_deep}+ sources")
            safe_print()

        # Initialize deep research planner
        planner = DeepResearchPlanner(
            gemini_model=model,
            min_sources=min_sources_deep,
            verbose=verbose
        )

        # #region agent log
        import json as json_lib
        import time as time_lib
        debug_log_path = "/tmp/opendraft_debug.log"
        try:
            with open(debug_log_path, "a") as f:
                f.write(json_lib.dumps({
                    "timestamp": int(time_lib.time() * 1000),
                    "location": "agent_runner.py:research_citations_via_api",
                    "message": "Starting deep research plan creation",
                    "data": {"topic": topic[:100]},
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception:
            pass
        # #endregion

        try:
            # Create research plan
            research_plan = planner.create_research_plan(
                topic=topic,
                scope=scope,
                seed_references=seed_references
            )

            # Validate plan quality
            if not planner.validate_plan(research_plan):
                if verbose:
                    safe_print("\n⚠️  Initial plan validation failed - attempting refinement...")

                # Attempt refinement
                research_plan = planner.refine_plan(
                    plan=research_plan,
                    feedback=f"Insufficient queries or coverage. Need minimum {min_sources_deep} sources. "
                            f"Generate more diverse queries covering: author searches, title searches, "
                            f"topic queries, regulatory/standards, and interdisciplinary connections."
                )

                # Validate again
                if not planner.validate_plan(research_plan):
                    raise ValueError(
                        f"Deep research plan validation failed after refinement. "
                        f"Generated {len(research_plan.get('queries', []))} queries, "
                        f"estimated {planner.estimate_coverage(research_plan.get('queries', []))} sources, "
                        f"but need minimum {min_sources_deep}."
                    )

            # Extract queries as research topics
            research_topics = research_plan.get('queries', [])

            if verbose:
                safe_print(f"\n✅ Research Plan Created:")
                safe_print(f"   Queries Generated: {len(research_topics)}")
                safe_print(f"   Estimated Coverage: {planner.estimate_coverage(research_topics)} sources")
                safe_print(f"\n📝 Research Strategy:")
                strategy_lines = research_plan.get('strategy', '').split('\n')
                for line in strategy_lines[:5]:  # First 5 lines
                    safe_print(f"   {line}")
                if len(strategy_lines) > 5:
                    safe_print(f"   ... (see output file for full strategy)")
                safe_print()
        
        except (TimeoutError, FuturesTimeoutError) as e:
            # Fallback to standard mode: generate basic queries from topic
            logger.warning(f"Deep research planning timed out, falling back to standard mode: {e}")
            if verbose:
                safe_print(f"\n⚠️  Deep Research Planning Timeout")
                safe_print(f"   Falling back to standard mode with basic queries...")
                safe_print()
            
            # #region agent log
            try:
                with open(debug_log_path, "a") as f:
                    f.write(json_lib.dumps({
                        "timestamp": int(time_lib.time() * 1000),
                        "location": "agent_runner.py:research_citations_via_api",
                        "message": "Deep research timeout - falling back to standard mode",
                        "data": {"error": str(e)[:200]},
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Generate basic queries from topic as fallback
            # Split topic into key terms and create simple queries
            topic_words = topic.split()
            # Create 10-15 basic queries covering different aspects
            research_topics = [
                topic,  # Full topic
                f"{topic} research",  # With "research"
                f"{topic} analysis",  # With "analysis"
                f"{topic} review",  # With "review"
                f"{topic} study",  # With "study"
            ]
            
            # Add queries for key terms if topic is long
            if len(topic_words) > 5:
                # Extract key phrases (first 3-4 words, middle 3-4 words, last 3-4 words)
                key_phrases = []
                if len(topic_words) >= 3:
                    key_phrases.append(" ".join(topic_words[:3]))
                if len(topic_words) >= 6:
                    key_phrases.append(" ".join(topic_words[2:5]))
                if len(topic_words) >= 4:
                    key_phrases.append(" ".join(topic_words[-3:]))
                
                research_topics.extend([f"{phrase} research" for phrase in key_phrases])
            
            # Ensure we have at least 10 queries
            while len(research_topics) < 10:
                research_topics.append(f"{topic} {len(research_topics)}")
            
            if verbose:
                safe_print(f"   Generated {len(research_topics)} fallback queries")
                safe_print()
        
        except Exception as e:
            # For other exceptions, also fallback to standard mode
            logger.warning(f"Deep research planning failed, falling back to standard mode: {e}")
            if verbose:
                safe_print(f"\n⚠️  Deep Research Planning Failed")
                safe_print(f"   Error: {str(e)[:200]}")
                safe_print(f"   Falling back to standard mode with basic queries...")
                safe_print()
            
            # #region agent log
            try:
                with open(debug_log_path, "a") as f:
                    f.write(json_lib.dumps({
                        "timestamp": int(time_lib.time() * 1000),
                        "location": "agent_runner.py:research_citations_via_api",
                        "message": "Deep research failed - falling back to standard mode",
                        "data": {"error": str(e)[:200]},
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Generate basic queries from topic as fallback
            topic_words = topic.split()
            research_topics = [
                topic,
                f"{topic} research",
                f"{topic} analysis",
                f"{topic} review",
                f"{topic} study",
            ]
            
            if len(topic_words) > 5:
                key_phrases = []
                if len(topic_words) >= 3:
                    key_phrases.append(" ".join(topic_words[:3]))
                if len(topic_words) >= 6:
                    key_phrases.append(" ".join(topic_words[2:5]))
                if len(topic_words) >= 4:
                    key_phrases.append(" ".join(topic_words[-3:]))
                research_topics.extend([f"{phrase} research" for phrase in key_phrases])
            
            while len(research_topics) < 10:
                research_topics.append(f"{topic} {len(research_topics)}")
            
            if verbose:
                safe_print(f"   Generated {len(research_topics)} fallback queries")
                safe_print()

    # Execution Phase: Run queries through API fallback chain
    if verbose:
        safe_print(f"\n📊 Execution Configuration:")
        safe_print(f"   Target Minimum: {target_minimum} citations")
        safe_print(f"   Research Topics/Queries: {len(research_topics)}")
        if output_path:
            safe_print(f"   Output: {output_path}")
        safe_print()

    # Initialize CitationResearcher with API fallback chain
    # Semantic Scholar can be disabled via env var if rate limited (403 errors)
    enable_semantic_scholar = os.environ.get('ENABLE_SEMANTIC_SCHOLAR', 'true').lower() != 'false'

    researcher = CitationResearcher(
        gemini_model=model,
        enable_crossref=True,
        enable_semantic_scholar=enable_semantic_scholar,
        enable_gemini_grounded=True,  # Enable for industry reports (McKinsey, Gartner, etc.)
        enable_smart_routing=True,     # Enable query classification for source diversity
        enable_llm_fallback=False,     # DISABLED: LLM hallucinates citations
        use_serper=True,               # Enable Serper API for web search fallback
        verbose=verbose,
        progress_callback=progress_callback,  # Pass through for progress reporting
    )

    if not enable_semantic_scholar and verbose:
        safe_print("   ⚠️  Semantic Scholar disabled (ENABLE_SEMANTIC_SCHOLAR=false)")

    # Track results
    citations: List[Citation] = []
    sources_breakdown: Dict[str, int] = {
        "Crossref": 0,
        "Semantic Scholar": 0,
        "Gemini Grounded": 0,
        "Gemini LLM": 0
    }
    failed_topics: List[str] = []

    # Parallel citation research configuration (tier-adaptive)
    config = get_concurrency_config(verbose=False)
    BATCH_SIZE = config.scout_batch_size
    BATCH_DELAY = config.scout_batch_delay
    PARALLEL_WORKERS = config.scout_parallel_workers

    # Detect if proxies are configured for rate limit bypass
    from utils.api_citations.base import PROXY_LIST
    use_proxies = len(PROXY_LIST) > 0

    # Adjust batch delay based on proxy availability
    # With proxies: skip delays for maximum throughput
    # Without proxies: respect API rate limits
    effective_batch_delay = 0 if use_proxies else BATCH_DELAY

    if verbose and use_proxies:
        safe_print(f"\n🔀 Proxy rotation enabled: {len(PROXY_LIST)} proxies")
        safe_print(f"   Batch delays disabled for maximum throughput")

    # Helper function for parallel execution with timeout
    def _research_single_topic(topic_with_idx: Tuple[int, str]) -> Tuple[int, str, List[Citation], Optional[str]]:
        """Research a single topic with timeout. Returns (idx, topic, list_of_citations, error_or_None)."""
        idx, research_topic = topic_with_idx
        try:
            # Wrap in executor for timeout control
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(researcher.research_citation, research_topic)
                try:
                    citations_list = future.result(timeout=per_topic_timeout_seconds)
                    return (idx, research_topic, citations_list, None)
                except FuturesTimeoutError:
                    return (idx, research_topic, [], f"Timeout after {per_topic_timeout_seconds}s")
        except Exception as e:
            return (idx, research_topic, [], str(e))

    # Early stopping at 50 citations
    early_stop_threshold = 50

    # Parallel or sequential based on config
    if PARALLEL_WORKERS > 1:
        if verbose:
            safe_print(f"\n🚀 Parallel citation research enabled ({PARALLEL_WORKERS} workers)")

        # Process in batches with parallel workers
        total_topics = len(research_topics)
        processed = 0

        for batch_start in range(0, total_topics, BATCH_SIZE):
            # Early stopping: Check if we've reached target + 10%
            if len(citations) >= early_stop_threshold:
                if verbose:
                    safe_print(f"\n⏩ Early stopping: {len(citations)} citations collected (target: {target_minimum}, threshold: {early_stop_threshold})")
                break

            batch_end = min(batch_start + BATCH_SIZE, total_topics)
            batch = list(enumerate(research_topics[batch_start:batch_end], batch_start + 1))

            if verbose and batch_start > 0 and effective_batch_delay > 0:
                safe_print(f"\n⏸️  Batch complete ({batch_start} topics processed). Waiting {effective_batch_delay}s to respect API limits...")
                time.sleep(effective_batch_delay)

            if verbose:
                safe_print(f"\n📦 Processing batch {batch_start // BATCH_SIZE + 1} ({len(batch)} topics)...")

            # Execute batch in parallel
            with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
                futures = {executor.submit(_research_single_topic, item): item for item in batch}

                for future in as_completed(futures):
                    idx, research_topic, citations_list, error = future.result()
                    processed += 1

                    if verbose:
                        safe_print(f"[{idx}/{total_topics}] 🔎 {research_topic[:55]}{'...' if len(research_topic) > 55 else ''}", end=' ')

                    if error:
                        failed_topics.append(research_topic)
                        if verbose:
                            safe_print(f"❌ Error: {error[:30]}...")
                        logger.error(f"Citation research failed for '{research_topic}': {error}")
                    elif citations_list:
                        # Add ALL citations from this query (multiple sources)
                        citations.extend(citations_list)
                        # Update source breakdown for all citations
                        for citation in citations_list:
                            source = citation.api_source or 'Unknown'
                            if source in sources_breakdown:
                                sources_breakdown[source] += 1
                        if verbose:
                            # Show all sources found for this query
                            sources_str = ", ".join([c.api_source or 'Unknown' for c in citations_list])
                            first_citation = citations_list[0]
                            authors_str = first_citation.authors[0] if first_citation.authors else "Unknown"
                            count_str = f" (+{len(citations_list)-1} more)" if len(citations_list) > 1 else ""
                            safe_print(f"✅ {authors_str} et al. ({first_citation.year}) [{sources_str}]{count_str}")

                        # Check for early stopping within batch
                        if len(citations) >= early_stop_threshold:
                            if verbose:
                                safe_print(f"\n⏩ Early stopping: {len(citations)} citations collected")
                            break
                    else:
                        failed_topics.append(research_topic)
                        if verbose:
                            safe_print("❌ No citation found")
    else:
        # Sequential execution (free tier or 1 worker)
        if verbose:
            safe_print("\n🔄 Sequential citation research (1 worker)")

        for idx, research_topic in enumerate(research_topics, 1):
            # Early stopping: Check if we've reached target + 10%
            if len(citations) >= early_stop_threshold:
                if verbose:
                    safe_print(f"\n⏩ Early stopping: {len(citations)} citations collected (target: {target_minimum}, threshold: {early_stop_threshold})")
                break

            # Add delay every BATCH_SIZE topics to prevent burst rate limits
            if idx > 1 and (idx - 1) % BATCH_SIZE == 0 and effective_batch_delay > 0:
                if verbose:
                    safe_print(f"\n⏸️  Batch complete ({idx-1} topics processed). Waiting {effective_batch_delay}s to respect API limits...")
                time.sleep(effective_batch_delay)

            if verbose:
                safe_print(f"[{idx}/{len(research_topics)}] 🔎 {research_topic[:65]}{'...' if len(research_topic) > 65 else ''}")

            try:
                # Wrap in executor for timeout control
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(researcher.research_citation, research_topic)
                    try:
                        citations_list = future.result(timeout=per_topic_timeout_seconds)
                    except FuturesTimeoutError:
                        citations_list = []
                        failed_topics.append(research_topic)
                        if verbose:
                            safe_print(f"    ⏱️  Timeout after {per_topic_timeout_seconds}s")
                        logger.warning(f"Citation research timed out for '{research_topic}' after {per_topic_timeout_seconds}s")
                        continue

                if citations_list:
                    # #region agent log
                    # Note: json, time, os already imported at module level
                    try:
                        debug_log_path = os.getenv('DEBUG_LOG_PATH', '/tmp/opendraft/debug.log')
                        os.makedirs(os.path.dirname(debug_log_path), exist_ok=True)
                        with open(debug_log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "J",
                                "location": "agent_runner.py:710",
                                "message": "Citations found for topic",
                                "data": {
                                    "topic": research_topic[:100],
                                    "citations_count": len(citations_list),
                                    "sources": [c.api_source or 'Unknown' for c in citations_list],
                                    "total_citations_so_far": len(citations) + len(citations_list)
                                },
                                "timestamp": int(time.time() * 1000)
                            }) + "\n")
                    except Exception as e:
                        logger.debug(f"Debug log write failed: {e}")
                    # #endregion
                    
                    # Add ALL citations from this query (multiple sources)
                    citations.extend(citations_list)

                    # Track sources for all citations
                    for citation in citations_list:
                        source = citation.api_source or 'Unknown'
                        if source in sources_breakdown:
                            sources_breakdown[source] += 1

                    if verbose:
                        # Show all sources found for this query
                        sources_str = ", ".join([c.api_source or 'Unknown' for c in citations_list])
                        first_citation = citations_list[0]
                        authors_str = first_citation.authors[0] if first_citation.authors else "Unknown"
                        count_str = f" (+{len(citations_list)-1} more)" if len(citations_list) > 1 else ""
                        safe_print(f"    ✅ {authors_str} et al. ({first_citation.year}) [{sources_str}]{count_str}")
                else:
                    failed_topics.append(research_topic)
                    if verbose:
                        safe_print(f"    ❌ No citation found")

            except Exception as e:
                failed_topics.append(research_topic)
                if verbose:
                    safe_print(f"    ❌ Error: {str(e)}")
                logger.error(f"Citation research failed for '{research_topic}': {str(e)}")

    # Calculate success metrics
    citation_count = len(citations)
    success_rate = (citation_count / len(research_topics) * 100) if research_topics else 0

    if verbose:
        safe_print("\n" + "=" * 80)
        safe_print("📊 SCOUT RESULTS")
        safe_print("=" * 80)
        safe_print(f"\n✅ Valid Citations: {citation_count}")
        safe_print(f"❌ Failed Topics: {len(failed_topics)}")
        safe_print(f"📈 Success Rate: {success_rate:.1f}%")
        safe_print(f"\n📚 Sources Breakdown:")
        for source, count in sources_breakdown.items():
            percentage = (count / citation_count * 100) if citation_count > 0 else 0
            safe_print(f"   {source}: {count} ({percentage:.1f}%)")
        safe_print()

    # Tiered Quality Gate
    excellent_threshold = target_minimum
    acceptable_threshold = int(target_minimum * 0.86)
    minimal_threshold = int(target_minimum * 0.70)

    # #region agent log
    # Note: json, time, os already imported at module level
    try:
        debug_log_path = os.getenv('DEBUG_LOG_PATH', '/tmp/opendraft/debug.log')
        with open(debug_log_path, 'a') as f:
            f.write(json.dumps({
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "G",
                "location": "agent_runner.py:760",
                "message": "Quality gate evaluation",
                "data": {
                    "citation_count": citation_count,
                    "target_minimum": target_minimum,
                    "excellent_threshold": excellent_threshold,
                    "acceptable_threshold": acceptable_threshold,
                    "minimal_threshold": minimal_threshold,
                    "sources_breakdown": sources_breakdown,
                    "failed_topics_count": len(failed_topics)
                },
                "timestamp": int(time.time() * 1000)
            }) + "\n")
    except Exception as e:
        logger.debug(f"Debug log write failed: {e}")
    # #endregion

    if citation_count >= excellent_threshold:
        if verbose:
            safe_print(f"✅ QUALITY GATE PASSED (EXCELLENT): {citation_count} ≥ {target_minimum} required\n")
        logger.info(f"Quality gate: EXCELLENT - {citation_count}/{target_minimum} citations")

    elif citation_count >= acceptable_threshold:
        percentage = (citation_count / target_minimum) * 100
        if verbose:
            safe_print(f"⚠️  QUALITY GATE PASSED (ACCEPTABLE): {citation_count}/{target_minimum} ({percentage:.1f}%)")
            safe_print(f"    Academic quality is good, but {target_minimum - citation_count} more citations recommended.\n")
        logger.warning(f"Quality gate: ACCEPTABLE - {citation_count}/{target_minimum} ({percentage:.1f}%)")

    elif citation_count >= minimal_threshold:
        percentage = (citation_count / target_minimum) * 100
        if verbose:
            safe_print(f"⚠️  QUALITY GATE PASSED (MINIMAL): {citation_count}/{target_minimum} ({percentage:.1f}%)")
            safe_print(f"    ⚠️  WARNING: Citation count is below recommended standards.")
            safe_print(f"    Consider adding {target_minimum - citation_count} more citations for better academic rigor.\n")
        logger.warning(f"Quality gate: MINIMAL - {citation_count}/{target_minimum} ({percentage:.1f}%) - below standards")

    else:
        percentage = (citation_count / target_minimum) * 100
        error_msg = (
            f"\n❌ QUALITY GATE FAILED (INSUFFICIENT CITATIONS)\n\n"
            f"Only {citation_count} citations found ({percentage:.1f}%), but minimum {minimal_threshold} required ({minimal_threshold/target_minimum*100:.0f}% of target).\n"
            f"Target: {target_minimum} citations (100%)\n"
            f"Acceptable: {acceptable_threshold}+ citations (86%)\n"
            f"Minimal: {minimal_threshold}+ citations (70%)\n"
            f"Current: {citation_count} citations ({percentage:.1f}%) ❌\n\n"
            f"Academic draft standards require at least {minimal_threshold} citations.\n\n"
            f"Failed Topics ({len(failed_topics)}):\n"
        )
        for failed_topic in failed_topics[:10]:
            error_msg += f"  - {failed_topic}\n"
        if len(failed_topics) > 10:
            error_msg += f"  ... and {len(failed_topics) - 10} more\n"

        logger.error(f"Quality gate FAILED: {citation_count} < {minimal_threshold} (minimal threshold)")
        raise ValueError(error_msg)

    # Format output as Scout-compatible markdown
    markdown_lines = [
        "# Scout Output - Academic Citation Discovery",
        "",
        "## Summary",
        "",
        f"**Total Valid Citations**: {citation_count}",
        f"**Success Rate**: {success_rate:.1f}%",
        f"**Failed Topics**: {len(failed_topics)}",
        "",
        "### Sources Breakdown",
        ""
    ]

    for source, count in sources_breakdown.items():
        percentage = (count / citation_count * 100) if citation_count > 0 else 0
        markdown_lines.append(f"- **{source}**: {count} ({percentage:.1f}%)")

    markdown_lines.extend([
        "",
        "---",
        "",
        "## Citations Found",
        ""
    ])

    # Add citations grouped by source
    for source in ["Crossref", "Semantic Scholar", "Gemini Grounded", "Gemini LLM"]:
        source_citations = [c for c in citations if c.api_source == source]
        if not source_citations:
            continue

        markdown_lines.append(f"### From {source} ({len(source_citations)} citations)")
        markdown_lines.append("")

        for idx, citation in enumerate(source_citations, 1):
            markdown_lines.append(f"#### {idx}. {citation.title}")
            markdown_lines.append(f"**Authors**: {', '.join(citation.authors)}")
            markdown_lines.append(f"**Year**: {citation.year}")
            markdown_lines.append(f"**DOI**: {citation.doi}")
            if citation.url:
                markdown_lines.append(f"**URL**: {citation.url}")
            if hasattr(citation, 'abstract') and citation.abstract:
                # Include abstract for Scribe to summarize (prevent hallucination)
                markdown_lines.append("")
                markdown_lines.append(f"**Abstract**: {citation.abstract}")
            markdown_lines.append("")

    if failed_topics:
        markdown_lines.extend([
            "---",
            "",
            "## Failed Topics",
            "",
            "The following topics did not return valid citations:",
            ""
        ])
        for failed_topic in failed_topics:
            markdown_lines.append(f"- {failed_topic}")

    # Write to file
    markdown_content = "\n".join(markdown_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_content, encoding='utf-8')

    if verbose:
        safe_print(f"💾 Saved Scout output to: {output_path}")
        safe_print(f"   File size: {output_path.stat().st_size:,} bytes\n")

    logger.info(f"Scout completed: {citation_count} citations, {success_rate:.1f}% success rate")

    return {
        "citations": citations,
        "count": citation_count,
        "sources": sources_breakdown,
        "failed_topics": failed_topics,
        "research_plan": research_plan
    }

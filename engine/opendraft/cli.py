#!/usr/bin/env python3
"""
OpenDraft CLI - AI-Powered Research Paper Generator

A simple, interactive command-line tool for generating academic papers.
"""

import sys

# Check Python version early (before any imports)
if sys.version_info < (3, 10):
    # Nice boxed error message
    PURPLE = '\033[95m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    print()
    print(f"  {PURPLE}╭─────────────────────────────────────────────────────────────╮{RESET}")
    print(f"  {PURPLE}│{RESET}                                                             {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {YELLOW}⚠️  OpenDraft requires Python 3.10 or higher{RESET}              {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}                                                             {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {GRAY}You have:{RESET} Python {sys.version_info.major}.{sys.version_info.minor}                                      {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}                                                             {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {BOLD}To fix, run:{RESET}                                              {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}                                                             {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {CYAN}conda create -n opendraft python=3.11 -y{RESET}                  {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {CYAN}conda activate opendraft{RESET}                                  {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}   {CYAN}pip install opendraft{RESET}                                     {PURPLE}│{RESET}")
    print(f"  {PURPLE}│{RESET}                                                             {PURPLE}│{RESET}")
    print(f"  {PURPLE}╰─────────────────────────────────────────────────────────────╯{RESET}")
    print()
    sys.exit(1)

# Suppress deprecation warnings from dependencies (Gemini SDK, weasyprint)
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress WeasyPrint's stderr warnings about missing libraries
import os
os.environ['WEASYPRINT_QUIET'] = '1'

# Minimal imports for fast startup
import json
from pathlib import Path

# Lazy import for version (fast, local file)
from opendraft.version import __version__

# Background module preloader for faster generation start
_preload_future = None

def _preload_modules():
    """Preload heavy modules in background."""
    try:
        import draft_generator
        import concurrent.futures
    except:
        pass

def start_preloading():
    """Start preloading modules in background thread."""
    global _preload_future
    if _preload_future is None:
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        _preload_future = executor.submit(_preload_modules)
        executor.shutdown(wait=False)

# Config directory for storing API keys and auth metadata
CONFIG_DIR = Path.home() / '.opendraft'
CONFIG_FILE = CONFIG_DIR / 'config.json'
AUTH_FILE = CONFIG_DIR / 'auth.json'

# ANSI color codes
class Colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    UNDERLINE = '\033[4m'


def get_friendly_error(e: Exception) -> tuple:
    """
    Convert technical exceptions to user-friendly messages.

    Returns:
        Tuple of (friendly_message, hint) or (None, None) if no friendly version
    """
    error_str = str(e).lower()
    error_type = type(e).__name__

    c = Colors

    # API Key errors
    if 'api key not valid' in error_str or 'invalid api key' in error_str:
        return (
            "Your API key is invalid or expired.",
            f"Run {c.CYAN}opendraft setup{c.RESET} to enter a new key."
        )

    if 'api_key_invalid' in error_str or 'permission_denied' in error_str:
        return (
            "API key doesn't have permission for this operation.",
            f"Check your key at {c.CYAN}https://aistudio.google.com/apikey{c.RESET}"
        )

    # Rate limiting
    if '429' in error_str or 'rate limit' in error_str or 'resource exhausted' in error_str or 'quota' in error_str:
        return (
            "Rate limited by the API.",
            "Wait a minute and try again. Free tier has usage limits."
        )

    # Network errors
    if 'connection' in error_str and ('error' in error_str or 'failed' in error_str):
        return (
            "Network connection failed.",
            "Check your internet connection and try again."
        )

    if 'timeout' in error_str:
        return (
            "Request timed out.",
            "The server took too long to respond. Try again."
        )

    if 'ssl' in error_str or 'certificate' in error_str:
        return (
            "Secure connection failed.",
            "Check your network/VPN settings and try again."
        )

    # DNS/hostname errors
    if 'name or service not known' in error_str or 'getaddrinfo failed' in error_str:
        return (
            "Can't reach the server.",
            "Check your internet connection."
        )

    # Content/safety filters
    if 'safety' in error_str or 'blocked' in error_str or 'harmful' in error_str:
        return (
            "Content was blocked by safety filters.",
            "Try rephrasing your topic or using different keywords."
        )

    # Model errors
    if 'model not found' in error_str or 'model' in error_str and 'not available' in error_str:
        return (
            "AI model is temporarily unavailable.",
            "Try again in a few minutes."
        )

    # Insufficient citations (common during research)
    if 'insufficient citations' in error_str:
        return (
            "Couldn't find enough sources for this topic.",
            "Try a more specific or different research topic."
        )

    # PDF/export errors
    if 'pdf' in error_str and ('failed' in error_str or 'error' in error_str):
        return (
            "PDF generation failed.",
            f"The Word document (.docx) should still be available."
        )

    if 'weasyprint' in error_str or 'cairo' in error_str or 'pango' in error_str:
        return (
            "PDF library not properly installed.",
            f"Run {c.CYAN}opendraft verify{c.RESET} to check dependencies."
        )

    # File/permission errors
    if 'permission denied' in error_str or 'errno 13' in error_str:
        return (
            "Permission denied when writing files.",
            "Try a different output directory or check folder permissions."
        )

    if 'no space' in error_str or 'disk full' in error_str:
        return (
            "Disk is full.",
            "Free up some space and try again."
        )

    # Memory errors
    if 'memory' in error_str or isinstance(e, MemoryError):
        return (
            "Ran out of memory.",
            "Close other apps and try again, or try a shorter topic."
        )

    # Recursion (rare but possible)
    if 'recursion' in error_str or 'maximum recursion' in error_str:
        return (
            "Something went wrong (recursion limit).",
            "Please report this at github.com/federicodeponte/opendraft/issues"
        )

    # JSON parsing errors (malformed API response)
    if 'json' in error_str and ('decode' in error_str or 'parse' in error_str):
        return (
            "Received invalid response from server.",
            "Try again in a few minutes."
        )

    # Encoding errors
    if 'encode' in error_str or 'decode' in error_str or 'codec' in error_str:
        return (
            "Text encoding error.",
            "Try using a simpler topic without special characters."
        )

    # File not found (missing dependency files)
    if 'no such file' in error_str or 'file not found' in error_str:
        return (
            "A required file is missing.",
            f"Try reinstalling: {c.CYAN}pip install --force-reinstall opendraft{c.RESET}"
        )

    # No friendly version found
    return (None, None)


def print_friendly_error(e: Exception):
    """Print a user-friendly error message for common exceptions."""
    c = Colors

    friendly_msg, hint = get_friendly_error(e)

    if friendly_msg:
        print()
        print(f"  {c.RED}✗{c.RESET} {friendly_msg}")
        if hint:
            print(f"    {c.GRAY}{hint}{c.RESET}")
        print()
    else:
        # Fallback: show original error but clean it up a bit
        error_str = str(e)
        # Remove common technical prefixes
        for prefix in ['google.api_core.exceptions.', 'requests.exceptions.',
                       'urllib3.exceptions.', 'httpx.']:
            error_str = error_str.replace(prefix, '')

        print()
        print(f"  {c.RED}✗{c.RESET} {error_str}")
        print()
        print(f"  {c.GRAY}If this keeps happening, report at:{c.RESET}")
        print(f"  {c.CYAN}https://github.com/federicodeponte/opendraft/issues{c.RESET}")
        print()


def get_saved_config():
    """Load saved configuration."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(config):
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_saved_auth() -> dict:
    """Load provider auth metadata/tokens stored separately from config."""
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_auth(auth_payload: dict) -> None:
    """Persist provider auth metadata/tokens outside config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(auth_payload, indent=2))


def clear_saved_openai_api_key(config: dict) -> dict:
    """Remove stale OpenAI API-key-style fields when using session auth."""
    config.pop('openai_api_key', None)
    return config


def get_active_provider() -> str:
    """Return the currently selected provider from env or saved config."""
    provider = (os.getenv('AI_PROVIDER') or get_saved_config().get('provider') or 'gemini').strip().lower()
    if provider in {'codex', 'openai-codex'}:
        return 'openai'
    return provider


def get_provider_label(provider: str) -> str:
    """Friendly provider label for the UI."""
    labels = {
        'gemini': 'Google Gemini',
        'openai': 'OpenAI',
    }
    return labels.get(provider, provider.title())


def get_active_auth_mode() -> str:
    """Return the currently selected auth mode for the active provider."""
    saved = get_saved_config()
    auth_mode = (os.getenv('OPENAI_AUTH_MODE') or saved.get('auth_mode') or 'api_key').strip().lower()
    if auth_mode in {'api', 'apikey', 'api-key'}:
        return 'api_key'
    if auth_mode in {'codex', 'openai-codex', 'browser'}:
        return 'openai-codex'
    return auth_mode


def get_provider_display_label(provider: str | None = None) -> str:
    """Return a UI label that includes the provider auth mode when useful."""
    provider = (provider or get_active_provider()).strip().lower()
    auth_mode = get_active_auth_mode() if provider == 'openai' else 'api_key'
    if provider == 'openai' and auth_mode == 'openai-codex':
        return 'OpenAI Codex'
    return get_provider_label(provider)


def apply_saved_runtime_config() -> None:
    """Sync saved config into environment variables for runtime use."""
    saved = get_saved_config()
    saved_auth = get_saved_auth()
    provider = (saved.get('provider') or os.getenv('AI_PROVIDER') or 'gemini').strip().lower()
    if provider in {'codex', 'openai-codex'}:
        provider = 'openai'
    os.environ['AI_PROVIDER'] = provider

    auth_mode = (saved.get('auth_mode') or os.getenv('OPENAI_AUTH_MODE') or 'api_key').strip().lower()
    if auth_mode in {'api', 'apikey', 'api-key'}:
        auth_mode = 'api_key'
    elif auth_mode in {'codex', 'openai-codex', 'browser'}:
        auth_mode = 'openai-codex'
    os.environ['OPENAI_AUTH_MODE'] = auth_mode

    if provider == 'gemini':
        api_key = saved.get('google_api_key') or saved.get('gemini_api_key') or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if api_key:
            os.environ['GOOGLE_API_KEY'] = api_key
            os.environ['GEMINI_API_KEY'] = api_key
    elif provider == 'openai':
        if auth_mode == 'openai-codex':
            codex_key = import_codex_auth_from_disk(save_to_config=True)
            if codex_key:
                os.environ['OPENAI_API_KEY'] = codex_key
            else:
                auth_token = _extract_string_credential(saved_auth)
                if auth_token:
                    os.environ['OPENAI_API_KEY'] = auth_token
        else:
            api_key = saved.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
            if api_key:
                os.environ['OPENAI_API_KEY'] = api_key


def get_codex_home() -> Path:
    """Return the Codex CLI home directory."""
    return Path(os.getenv('CODEX_HOME') or (Path.home() / '.codex'))


def get_codex_binary() -> str | None:
    """Resolve the Codex CLI binary path if installed."""
    import shutil

    for candidate in (shutil.which('codex'), Path.home() / '.local' / 'node_modules' / '.bin' / 'codex', Path.home() / '.npm-global' / 'bin' / 'codex'):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def ensure_codex_file_auth_storage(codex_home: Path) -> Path:
    """Ensure Codex stores credentials in local files so Hermes/OpenDraft can import them."""
    codex_home.mkdir(parents=True, exist_ok=True)
    config_path = codex_home / 'config.toml'
    line = 'cli_auth_credentials_store = "file"\n'
    if config_path.exists():
        current = config_path.read_text(encoding='utf-8')
        if 'cli_auth_credentials_store' not in current:
            current = current.rstrip() + '\n' + line
            config_path.write_text(current, encoding='utf-8')
    else:
        config_path.write_text(line, encoding='utf-8')
    return config_path


def _tokenish(value: str) -> bool:
    return isinstance(value, str) and len(value.strip()) >= 20


def _extract_string_credential(payload):
    """Recursively search nested auth payloads for a usable credential string."""
    preferred_keys = (
        'openai_api_key', 'api_key', 'apikey', 'access_token', 'token', 'bearer_token',
        'session_token', 'refresh_token', 'key', 'secret', 'auth_token', 'credential',
    )

    if isinstance(payload, dict):
        for key in preferred_keys:
            value = payload.get(key)
            if _tokenish(value):
                return value.strip()
        for value in payload.values():
            found = _extract_string_credential(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_string_credential(item)
            if found:
                return found
    elif _tokenish(payload):
        return str(payload).strip()
    return None


def import_codex_auth_from_disk(save_to_config: bool = True) -> str | None:
    """Import a Codex CLI auth artifact into OpenDraft runtime env/auth store."""
    codex_home = get_codex_home()
    auth_file = codex_home / 'auth.json'
    if not auth_file.exists():
        return None

    try:
        payload = json.loads(auth_file.read_text(encoding='utf-8'))
    except Exception:
        return None

    credential = _extract_string_credential(payload)
    if not credential:
        return None

    os.environ['OPENAI_API_KEY'] = credential
    os.environ['OPENAI_AUTH_MODE'] = 'openai-codex'

    if save_to_config:
        config = clear_saved_openai_api_key(get_saved_config())
        config['provider'] = 'openai'
        config['auth_mode'] = 'openai-codex'
        config['codex_home'] = str(codex_home)
        config['codex_auth_file'] = str(auth_file)
        save_config(config)
        save_auth({
            'provider': 'openai',
            'auth_mode': 'openai-codex',
            'codex_home': str(codex_home),
            'codex_auth_file': str(auth_file),
            'credential': credential,
            'imported_from': str(auth_file),
        })

    return credential


def run_codex_login_flow() -> tuple[bool, str]:
    """Run the real Codex CLI browser login flow and import the resulting auth."""
    import subprocess

    codex_bin = get_codex_binary()
    if not codex_bin:
        return False, 'Codex CLI not found on PATH. Install it first, then retry.'

    codex_home = get_codex_home()
    config_path = ensure_codex_file_auth_storage(codex_home)
    env = os.environ.copy()
    env['CODEX_HOME'] = str(codex_home)
    env['OPENAI_AUTH_MODE'] = 'openai-codex'

    try:
        result = subprocess.run([codex_bin, 'login'], env=env)
    except FileNotFoundError:
        return False, f'Could not execute Codex CLI at {codex_bin}'
    except KeyboardInterrupt:
        return False, 'Codex login cancelled.'

    if result.returncode != 0:
        return False, f'Codex login failed with exit code {result.returncode}'

    credential = import_codex_auth_from_disk(save_to_config=True)
    if credential:
        return True, f'Codex session imported from {config_path.parent / "auth.json"}'

    return False, f'Codex login finished, but no usable auth.json was found in {codex_home}'


def get_provider_key(provider: str | None = None) -> str:
    """Get API key for a provider from environment or saved config."""
    provider = (provider or get_active_provider()).strip().lower()
    if provider in {'codex', 'openai-codex'}:
        provider = 'openai'
    saved = get_saved_config()
    if provider == 'gemini':
        return os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') or saved.get('google_api_key', '') or saved.get('gemini_api_key', '')
    if provider == 'openai':
        return os.getenv('OPENAI_API_KEY') or saved.get('openai_api_key', '')
    return ''


def has_api_key(provider: str | None = None):
    """Check if the selected provider has credentials configured."""
    return bool(get_provider_key(provider))


def get_api_key(provider: str | None = None):
    """Get the selected provider API key from environment or config."""
    return get_provider_key(provider)


def clear_screen():
    """Clear terminal screen."""
    import subprocess
    try:
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'cls'], check=False)
        else:
            subprocess.run(['clear'], check=False)
    except (FileNotFoundError, OSError):
        # Fallback: print newlines if clear command not available
        print('\n' * 50)


def print_logo():
    """Print ASCII art logo."""
    c = Colors
    logo = f"""
{c.PURPLE}{c.BOLD}  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │   ██████╗ ██████╗ ███████╗███╗   ██╗               │
  │  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║               │
  │  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║               │
  │  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║               │
  │  ╚██████╔╝██║     ███████╗██║ ╚████║               │
  │   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝               │
  │  ██████╗ ██████╗  █████╗ ███████╗████████╗         │
  │  ██╔══██╗██╔══██╗██╔══██╗██╔════╝╚══██╔══╝         │
  │  ██║  ██║██████╔╝███████║█████╗     ██║            │
  │  ██║  ██║██╔══██╗██╔══██║██╔══╝     ██║            │
  │  ██████╔╝██║  ██║██║  ██║██║        ██║            │
  │  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝            │
  │                                                     │
  └─────────────────────────────────────────────────────┘{c.RESET}
"""
    print(logo)


def print_header():
    """Print clean header with logo."""
    c = Colors
    provider = get_active_provider()
    print_logo()
    print(f"  {c.GRAY}AI Research Paper Generator{c.RESET}  {c.DIM}v{__version__}{c.RESET}")
    print(f"  {c.GRAY}Provider:{c.RESET} {get_provider_display_label(provider)}")
    auth_mode = get_active_auth_mode() if provider == 'openai' else 'api_key'
    if provider == 'openai':
        print(f"  {c.GRAY}Auth mode:{c.RESET} {auth_mode.replace('-', ' ').title()}")
    print()


def print_divider():
    """Print a subtle divider."""
    print(f"  {Colors.GRAY}{'─' * 50}{Colors.RESET}")


def run_setup():
    """Interactive setup wizard with provider choice."""
    c = Colors
    clear_screen()
    print_header()

    print(f"  {c.BOLD}Setup{c.RESET}")
    print_divider()
    print()

    current_provider = get_active_provider()
    provider_default = 1 if current_provider == 'openai' else 0
    provider = select_option(
        "Choose AI provider",
        [
            ("Google Gemini", "gemini"),
            ("OpenAI Codex / OpenAI", "openai"),
        ],
        default=provider_default,
    )
    if provider is None:
        return False

    auth_mode = 'api_key'
    if provider == 'openai':
        print()
        auth_mode = select_option(
            "Choose OpenAI auth method",
            [
                ("OpenAI API key", "api_key"),
                ("OpenAI Codex login (browser / session)", "openai-codex"),
            ],
            default=0,
        )
        if auth_mode is None:
            return False

        if auth_mode == 'api_key':
            print(f"  {c.BOLD}OpenAI Codex / OpenAI setup{c.RESET}")
            print(f"  You need an {c.BOLD}OpenAI API key{c.RESET}.")
            api_url = "https://platform.openai.com/api-keys"
            key_label = "OpenAI API Key"
            env_name = 'OPENAI_API_KEY'
            saved_key_name = 'openai_api_key'
            print()
            try:
                import webbrowser
                webbrowser.open(api_url)
                print(f"  {c.GREEN}✓{c.RESET} Opened {c.UNDERLINE}{api_url}{c.RESET} in browser")
            except Exception:
                print(f"  {c.CYAN}1.{c.RESET} Open {c.UNDERLINE}{api_url}{c.RESET}")

            print()
            print(f"  {c.CYAN}→{c.RESET} Paste the key below")
            print()

            try:
                api_key = input(f"  {c.PURPLE}›{c.RESET} {key_label}: ").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
                return False

            if not api_key:
                print(f"\n  {c.RED}✗{c.RESET} No key provided.\n")
                return False

            if len(api_key) < 20:
                print(f"\n  {c.RED}✗{c.RESET} Invalid key format.\n")
                return False
        else:
            print(f"  {c.BOLD}OpenAI Codex login{c.RESET}")
            print(f"  Browser-based Codex auth will start now.")
            print(f"  The CLI should open your browser and ask you to sign in/approve.")
            print(f"  After success, OpenDraft will import the local Codex session.")
            print()
            success, message = run_codex_login_flow()
            if not success:
                print(f"  {c.RED}✗{c.RESET} {message}")
                print()
                return False
            print(f"  {c.GREEN}✓{c.RESET} {message}")
            print()
            api_key = os.getenv('OPENAI_API_KEY') or get_saved_config().get('openai_api_key', '').strip()
            env_name = 'OPENAI_API_KEY'
            saved_key_name = 'openai_api_key'
    else:
        print(f"  {c.BOLD}Gemini setup{c.RESET}")
        print(f"  You need a {c.BOLD}Google AI API key{c.RESET} (free).")
        api_url = "https://aistudio.google.com/apikey"
        key_label = "Google AI API Key"
        env_name = 'GOOGLE_API_KEY'
        saved_key_name = 'google_api_key'
        print()
        try:
            import webbrowser
            webbrowser.open(api_url)
            print(f"  {c.GREEN}✓{c.RESET} Opened {c.UNDERLINE}{api_url}{c.RESET} in browser")
        except Exception:
            print(f"  {c.CYAN}1.{c.RESET} Open {c.UNDERLINE}{api_url}{c.RESET}")

        print()
        print(f"  {c.CYAN}→{c.RESET} Paste the key below")
        print()

        try:
            api_key = input(f"  {c.PURPLE}›{c.RESET} {key_label}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
            return False

        if not api_key:
            print(f"\n  {c.RED}✗{c.RESET} No key provided.\n")
            return False

        if len(api_key) < 20:
            print(f"\n  {c.RED}✗{c.RESET} Invalid key format.\n")
            return False

    config = get_saved_config()
    config['provider'] = provider
    config['auth_mode'] = auth_mode
    if api_key:
        config[saved_key_name] = api_key
    if provider == 'gemini' and api_key:
        # Keep backwards compatibility with older config files.
        config['google_api_key'] = api_key
    save_config(config)

    os.environ['AI_PROVIDER'] = provider
    os.environ['OPENAI_AUTH_MODE'] = auth_mode
    if api_key:
        os.environ[env_name] = api_key
    if provider == 'gemini' and api_key:
        os.environ['GOOGLE_API_KEY'] = api_key
        os.environ['GEMINI_API_KEY'] = api_key

    print()
    print(f"  {c.GREEN}✓{c.RESET} Saved provider: {get_provider_label(provider)}")
    print(f"  {c.GREEN}✓{c.RESET} Auth mode: {auth_mode.replace('-', ' ').title()}")
    if api_key:
        print(f"  {c.GREEN}✓{c.RESET} API key saved to {c.GRAY}~/.opendraft/config.json{c.RESET}")
    else:
        print(f"  {c.YELLOW}!{c.RESET} No API key saved; runtime will use your shell env if available.")
    print()
    return True


def select_option(prompt, options, default=0):
    """Clean option selector with visible numbers."""
    c = Colors
    print(f"  {c.PURPLE}›{c.RESET} {prompt}")
    print()

    for i, (label, value) in enumerate(options):
        num = i + 1
        if i == default:
            print(f"    {c.PURPLE}{num}.{c.RESET} {c.BOLD}{label}{c.RESET} {c.GRAY}← default{c.RESET}")
        else:
            print(f"    {c.GRAY}{num}. {label}{c.RESET}")
    print()

    try:
        choice = input(f"  {c.GRAY}Enter 1-{len(options)} or press Enter:{c.RESET} ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    selected_idx = default
    if choice:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                selected_idx = idx
        except ValueError:
            pass

    # Show what was selected
    selected_label = options[selected_idx][0]
    print(f"  {c.GREEN}✓{c.RESET} {selected_label}")
    print()

    return options[selected_idx][1]


def run_interactive():
    """Run interactive paper generation."""
    c = Colors
    clear_screen()
    print_header()

    # Start preloading heavy modules in background while user fills options
    start_preloading()

    apply_saved_runtime_config()

    # Check for API key
    if not has_api_key():
        print(f"  {c.YELLOW}!{c.RESET} No API key configured.")
        print()
        if not run_setup():
            return 1
        clear_screen()
        print_header()
    else:
        if not os.getenv('GOOGLE_API_KEY'):
            os.environ['GOOGLE_API_KEY'] = get_api_key()

    print(f"  {c.BOLD}New Paper{c.RESET}")
    print_divider()
    print()

    # Get topic
    try:
        print(f"  {c.PURPLE}›{c.RESET} What's your research topic?")
        print()
        topic = input(f"    ").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
        return 0

    if not topic:
        print(f"\n  {c.RED}✗{c.RESET} No topic provided.\n")
        return 1

    print()

    # Get optional research blurb
    print(f"  {c.PURPLE}›{c.RESET} Research focus {c.GRAY}(optional - press Enter to skip){c.RESET}")
    print(f"    {c.GRAY}Add context like specific aspects, hypotheses, or constraints{c.RESET}")
    print()
    try:
        blurb = input(f"    ").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
        return 0

    if blurb:
        print(f"  {c.GREEN}✓{c.RESET} Focus: {blurb[:60]}{'...' if len(blurb) > 60 else ''}")
    print()

    # Select level
    level = select_option(
        "Academic level",
        [
            ("Research paper", "research_paper"),
            ("Bachelor's thesis", "bachelor"),
            ("Master's thesis", "master"),
            ("PhD dissertation", "phd"),
        ],
        default=0
    )
    if level is None:
        return 0

    # Select output type
    output_type = select_option(
        "Output type",
        [
            ("Full draft (complete paper)", "full"),
            ("Research exposé (outline + sources, faster)", "expose"),
        ],
        default=0
    )
    if output_type is None:
        return 0

    # Select citation style
    style = select_option(
        "Citation style",
        [
            ("APA 7th Edition", "apa"),
            ("IEEE", "ieee"),
            ("Chicago (Author-Date)", "chicago"),
            ("MLA 9th Edition", "mla"),
        ],
        default=0
    )
    if style is None:
        return 0

    # Select language (expanded options)
    language = select_option(
        "Language",
        [
            ("English", "en"),
            ("German (Deutsch)", "de"),
            ("Spanish (Español)", "es"),
            ("French (Français)", "fr"),
            ("Other...", "other"),
        ],
        default=0
    )
    if language is None:
        return 0

    # Handle custom language input
    if language == "other":
        print(f"  {c.GRAY}Codes: it, pt, nl, zh, ja, ko, ru, ar, sv, no, pl, etc.{c.RESET}")
        try:
            language = input(f"  {c.PURPLE}›{c.RESET} Language code: ").strip().lower() or "en"
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
            return 0

    # Language display names
    lang_names = {
        'en': 'English', 'de': 'German', 'es': 'Spanish', 'fr': 'French',
        'it': 'Italian', 'pt': 'Portuguese', 'nl': 'Dutch', 'zh': 'Chinese',
        'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian', 'ar': 'Arabic'
    }

    # Optional: Cover page details
    print(f"  {c.PURPLE}›{c.RESET} Add cover page details? {c.GRAY}(for thesis formatting){c.RESET}")
    print(f"    {c.GRAY}Adds author, institution, advisor to title page{c.RESET}")
    print()
    try:
        add_cover = input(f"    {c.GRAY}[y/N]{c.RESET} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
        return 0

    author_name = None
    institution = None
    department = None
    advisor = None

    if add_cover in ['y', 'yes']:
        print()
        print(f"  {c.GRAY}Press Enter to skip any field{c.RESET}")
        print()

        try:
            author_name = input(f"  {c.PURPLE}›{c.RESET} Your name: ").strip() or None
            institution = input(f"  {c.PURPLE}›{c.RESET} Institution: ").strip() or None
            department = input(f"  {c.PURPLE}›{c.RESET} Department: ").strip() or None
            advisor = input(f"  {c.PURPLE}›{c.RESET} Advisor/Supervisor: ").strip() or None
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
            return 0

        if any([author_name, institution, department, advisor]):
            print(f"  {c.GREEN}✓{c.RESET} Cover page details added")
        print()

    # Confirm
    print_divider()
    print()
    level_display = level.replace("_", " ").title()
    lang_display = lang_names.get(language, language.upper())
    output_display = "Research Exposé" if output_type == 'expose' else "Full Draft"
    print(f"  {c.GRAY}Topic{c.RESET}     {topic}")
    if blurb:
        print(f"  {c.GRAY}Focus{c.RESET}     {blurb[:50]}{'...' if len(blurb) > 50 else ''}")
    print(f"  {c.GRAY}Level{c.RESET}     {level_display}")
    print(f"  {c.GRAY}Mode{c.RESET}      {output_display}")
    print(f"  {c.GRAY}Style{c.RESET}     {style.upper()}")
    print(f"  {c.GRAY}Language{c.RESET}  {lang_display}")
    if author_name:
        print(f"  {c.GRAY}Author{c.RESET}    {author_name}")
    if institution:
        print(f"  {c.GRAY}Institution{c.RESET} {institution}")
    print()
    print_divider()
    print()

    confirm_prompt = "Generate exposé?" if output_type == 'expose' else "Generate paper?"
    try:
        confirm = input(f"  {c.PURPLE}›{c.RESET} {confirm_prompt} {c.GRAY}[Y/n]{c.RESET} ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n  {c.GRAY}Cancelled.{c.RESET}\n")
        return 0

    if confirm and confirm not in ['y', 'yes', '']:
        print(f"\n  {c.GRAY}Cancelled.{c.RESET}\n")
        return 0

    # Start generation
    print()
    print_divider()
    print()
    if output_type == 'expose':
        print(f"  {c.PURPLE}⣾{c.RESET} {c.BOLD}Starting research exposé...{c.RESET}")
    else:
        print(f"  {c.PURPLE}⣾{c.RESET} {c.BOLD}Starting paper generation...{c.RESET}")
    print(f"  {c.GRAY}Loading AI modules...{c.RESET}", end='', flush=True)

    try:
        from draft_generator import generate_draft
        from utils.logging_config import enable_cli_mode
        print(f" {c.GREEN}✓{c.RESET}")

        # Enable user-friendly logging (hide timestamps, module names)
        enable_cli_mode()
        # NOTE: We keep research verbosity ON so users can see outline, sources, and progress

        print()
        print(f"  {c.CYAN}{'━' * 50}{c.RESET}")
        print(f"  {c.BOLD}🚀 Starting research on:{c.RESET} {topic[:50]}{'...' if len(topic) > 50 else ''}")
        print(f"  {c.CYAN}{'━' * 50}{c.RESET}")
        print()
        if output_type == 'expose':
            print(f"  {c.GRAY}Generating research exposé (2-5 minutes)...{c.RESET}")
        else:
            print(f"  {c.GRAY}This typically takes 10-15 minutes.{c.RESET}")
        print(f"  {c.GRAY}You'll see progress updates below.{c.RESET}")
        print()

        output_dir = Path.cwd() / 'opendraft_output'

        pdf_path, docx_path = generate_draft(
            topic=topic,
            language=language,
            academic_level=level,
            output_dir=output_dir,
            skip_validation=True,
            verbose=True,
            blurb=blurb if blurb else None,
            output_type=output_type,
            author_name=author_name,
            institution=institution,
            department=department,
            advisor=advisor,
            citation_style=style,
        )

        print()
        print_divider()
        print()
        print(f"  {c.GREEN}{'━' * 40}{c.RESET}")
        if output_type == 'expose':
            print(f"  {c.GREEN}✓{c.RESET} {c.BOLD}Your research exposé is ready!{c.RESET}")
        else:
            print(f"  {c.GREEN}✓{c.RESET} {c.BOLD}Your paper is ready!{c.RESET}")
        print(f"  {c.GREEN}{'━' * 40}{c.RESET}")
        print()

        # Show file paths
        exports_dir = output_dir / 'exports'
        print(f"  {c.GRAY}Files saved to:{c.RESET}")
        print(f"  {exports_dir}")
        print()
        print(f"  {c.CYAN}📄{c.RESET} {pdf_path.name}")
        print(f"  {c.CYAN}📝{c.RESET} {docx_path.name}")

        # Check for ZIP
        zip_path = exports_dir / f"{pdf_path.stem}.zip"
        if zip_path.exists():
            print(f"  {c.CYAN}📦{c.RESET} {zip_path.name}")
        print()

        # Open output folder
        try:
            import subprocess
            if sys.platform == 'darwin':
                subprocess.run(['open', str(exports_dir)], check=False)
            elif sys.platform == 'win32':
                subprocess.run(['explorer', str(exports_dir)], check=False)
            elif sys.platform.startswith('linux'):
                subprocess.run(['xdg-open', str(exports_dir)], check=False)
            print(f"  {c.GRAY}Folder opened automatically.{c.RESET}")
        except:
            pass

        print()
        return 0

    except KeyboardInterrupt:
        print(f"\n\n  {c.YELLOW}!{c.RESET} Generation interrupted.\n")
        return 1
    except Exception as e:
        print_friendly_error(e)
        return 1


def run_tldr_command(argv):
    """Run TL;DR subcommand."""
    import argparse
    c = Colors

    parser = argparse.ArgumentParser(
        prog="opendraft tldr",
        description="Generate 5-bullet TL;DR summary for any paper"
    )
    parser.add_argument("document", help="Path to document (PDF, MD, or TXT)")
    parser.add_argument("--output", "-o", help="Output file path")

    args = parser.parse_args(argv)
    document_path = Path(args.document)

    if not document_path.exists():
        print(f"\n  {c.RED}✗{c.RESET} File not found: {document_path}\n")
        return 1

    print()
    print(f"  {c.BOLD}TL;DR{c.RESET}")
    print(f"  {c.GRAY}{'─' * 40}{c.RESET}")
    print(f"  {c.GRAY}Document:{c.RESET} {document_path.name}")

    try:
        # Import here to avoid slow startup
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from tldr import generate_tldr
        from utils.document_reader import get_document_info

        info = get_document_info(document_path)
        print(f"  {c.GRAY}Words:{c.RESET}    {info['word_count']:,}")
        print()
        print(f"  {c.PURPLE}⣾{c.RESET} Generating TL;DR...")

        tldr = generate_tldr(document_path)

        print()
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")
        # Print TL;DR with nice formatting
        for line in tldr.split('\n'):
            if line.strip():
                print(f"  {line}")
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(tldr, encoding="utf-8")
            print(f"\n  {c.GREEN}✓{c.RESET} Saved to: {output_path}")

        print()
        return 0

    except Exception as e:
        print_friendly_error(e)
        return 1


def run_digest_command(argv):
    """Run digest subcommand."""
    import argparse
    c = Colors

    parser = argparse.ArgumentParser(
        prog="opendraft digest",
        description="Generate 60-second audio digest for any paper"
    )
    parser.add_argument("document", help="Path to document (PDF, MD, or TXT)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument(
        "--voice",
        default="rachel",
        choices=["rachel", "adam", "josh", "elli", "bella"],
        help="ElevenLabs voice (default: rachel)"
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio generation (script only)"
    )

    args = parser.parse_args(argv)
    document_path = Path(args.document)

    if not document_path.exists():
        print(f"\n  {c.RED}✗{c.RESET} File not found: {document_path}\n")
        return 1

    print()
    print(f"  {c.BOLD}Digest{c.RESET}")
    print(f"  {c.GRAY}{'─' * 40}{c.RESET}")
    print(f"  {c.GRAY}Document:{c.RESET} {document_path.name}")
    print(f"  {c.GRAY}Voice:{c.RESET}    {args.voice}")

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from digest import generate_digest
        from utils.document_reader import get_document_info

        info = get_document_info(document_path)
        print(f"  {c.GRAY}Words:{c.RESET}    {info['word_count']:,}")
        print()
        print(f"  {c.PURPLE}⣾{c.RESET} Generating digest...")

        output_dir = Path(args.output) if args.output else None

        result = generate_digest(
            document_path,
            output_dir=output_dir,
            voice=args.voice,
            generate_audio=not args.no_audio,
        )

        print()
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")
        print(f"  {result['script']}")
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")
        print()
        print(f"  {c.GRAY}Words:{c.RESET} {result['word_count']}")
        print(f"  {c.GREEN}✓{c.RESET} Script: {result['script_path']}")

        if "audio_path" in result:
            print(f"  {c.GREEN}✓{c.RESET} Audio:  {result['audio_path']}")
        elif "audio_error" in result:
            print(f"  {c.YELLOW}!{c.RESET} Audio skipped: {result['audio_error']}")
            print(f"    {c.GRAY}Set ELEVENLABS_API_KEY to enable audio{c.RESET}")

        print()
        return 0

    except Exception as e:
        print_friendly_error(e)
        return 1


def run_revise_command(argv):
    """Run revise subcommand."""
    import argparse
    c = Colors

    parser = argparse.ArgumentParser(
        prog="opendraft revise",
        description="Revise an existing draft with AI assistance"
    )
    parser.add_argument("target", help="Path to draft folder or markdown file")
    parser.add_argument("instructions", help="Revision instructions (e.g., 'make the introduction longer')")
    parser.add_argument("--model", "-m", default="gemini-3-flash-preview",
                        help="Gemini model to use (default: gemini-3-flash-preview)")

    args = parser.parse_args(argv)
    target_path = Path(args.target)

    if not target_path.exists():
        print(f"\n  {c.RED}✗{c.RESET} Path not found: {target_path}\n")
        return 1

    print()
    print(f"  {c.BOLD}Revise{c.RESET}")
    print(f"  {c.GRAY}{'─' * 40}{c.RESET}")
    print(f"  {c.GRAY}Target:{c.RESET}       {target_path}")
    print(f"  {c.GRAY}Instructions:{c.RESET} {args.instructions[:50]}{'...' if len(args.instructions) > 50 else ''}")
    print()

    # Ensure API key is set
    if not has_api_key():
        print(f"  {c.YELLOW}!{c.RESET} Run {c.BOLD}opendraft setup{c.RESET} first.\n")
        return 1

    if not os.getenv('GOOGLE_API_KEY'):
        os.environ['GOOGLE_API_KEY'] = get_api_key()

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.revise import revise_draft, find_draft_in_folder

        # Show which file will be revised
        if target_path.is_dir():
            draft_path = find_draft_in_folder(target_path)
            if draft_path:
                print(f"  {c.GRAY}Found draft:{c.RESET} {draft_path.name}")
            else:
                print(f"\n  {c.RED}✗{c.RESET} No draft found in {target_path}\n")
                return 1
        print()
        print(f"  {c.PURPLE}⣾{c.RESET} Revising draft...")

        result = revise_draft(target_path, args.instructions, model=args.model)

        print()
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")
        print(f"  {c.GREEN}✓{c.RESET} {c.BOLD}Revision complete!{c.RESET}")
        print(f"  {c.GREEN}{'─' * 40}{c.RESET}")
        print()

        # Score changes
        delta_color = c.GREEN if result['delta'] >= 0 else c.RED
        delta_sign = "+" if result['delta'] >= 0 else ""
        print(f"  {c.GRAY}Quality:{c.RESET} {result['score_before']} → {result['score_after']} ({delta_color}{delta_sign}{result['delta']}{c.RESET})")
        print(f"  {c.GRAY}Words:{c.RESET}   {result['word_count_before']:,} → {result['word_count']:,}")

        print()
        print(f"  {c.GRAY}Files:{c.RESET}")
        print(f"    {c.CYAN}📝{c.RESET} {result['md_path']}")
        if result['pdf_path']:
            print(f"    {c.CYAN}📄{c.RESET} {result['pdf_path']}")
        if result['docx_path']:
            print(f"    {c.CYAN}📑{c.RESET} {result['docx_path']}")
        print()

        return 0

    except Exception as e:
        print_friendly_error(e)
        return 1


def run_data_command(argv):
    """Run data subcommand for fetching research datasets."""
    import argparse
    c = Colors

    parser = argparse.ArgumentParser(
        prog="opendraft data",
        description="Fetch research data from World Bank, Eurostat, or Our World in Data"
    )
    parser.add_argument("provider", choices=["worldbank", "eurostat", "owid", "search", "list"],
                        help="Data provider or 'list' to show providers")
    parser.add_argument("query", nargs="?", help="Indicator code or dataset name")
    parser.add_argument("--countries", "-c", default="all",
                        help="Countries for World Bank (semicolon-separated codes, e.g., 'USA;DEU;FRA')")
    parser.add_argument("--start", "-s", type=int, help="Start year")
    parser.add_argument("--end", "-e", type=int, help="End year")
    parser.add_argument("--output", "-o", type=Path, default=Path.cwd(),
                        help="Output directory (default: current directory)")

    args = parser.parse_args(argv)

    print()
    print(f"  {c.BOLD}Data Fetch{c.RESET}")
    print(f"  {c.GRAY}{'─' * 40}{c.RESET}")

    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.data_fetch import DataFetcher, SDMX_PROVIDERS

        # List providers
        if args.provider == "list":
            print(f"\n  {c.BOLD}Available Data Providers{c.RESET}\n")
            for key, info in SDMX_PROVIDERS.items():
                print(f"  {c.CYAN}{key:12}{c.RESET} {info['name']} - {info['description']}")
            print()
            print(f"  {c.GRAY}Examples:{c.RESET}")
            print(f"    opendraft data search GDP")
            print(f"    opendraft data worldbank NY.GDP.MKTP.CD --countries USA;DEU;FRA")
            print(f"    opendraft data owid covid-19")
            print(f"    opendraft data eurostat nama_10_gdp")
            print()
            return 0

        if not args.query:
            print(f"\n  {c.RED}✗{c.RESET} Query/indicator required for provider '{args.provider}'\n")
            return 1

        fetcher = DataFetcher(args.output)

        print(f"  {c.GRAY}Provider:{c.RESET} {args.provider}")
        print(f"  {c.GRAY}Query:{c.RESET}    {args.query}")
        print()
        print(f"  {c.PURPLE}⣾{c.RESET} Fetching data...")

        # Execute fetch
        if args.provider == "worldbank":
            result = fetcher.fetch_worldbank(
                args.query,
                countries=args.countries,
                start_year=args.start,
                end_year=args.end,
            )
        elif args.provider == "eurostat":
            result = fetcher.fetch_eurostat(
                args.query,
                start_period=str(args.start) if args.start else None,
                end_period=str(args.end) if args.end else None,
            )
        elif args.provider == "owid":
            result = fetcher.fetch_owid(args.query)
        elif args.provider == "search":
            result = fetcher.search_worldbank(args.query)
        else:
            result = {"status": "error", "message": f"Unknown provider: {args.provider}"}

        print()

        if result.get("status") == "success":
            print(f"  {c.GREEN}✓{c.RESET} {result.get('message', 'Success')}")
            print()

            if "file_path" in result:
                print(f"  {c.GRAY}Saved to:{c.RESET} {result['file_path']}")
            if "rows" in result:
                print(f"  {c.GRAY}Rows:{c.RESET}     {result['rows']:,}")
            if "countries" in result:
                print(f"  {c.GRAY}Countries:{c.RESET} {result['countries']}")
            if "years" in result:
                print(f"  {c.GRAY}Years:{c.RESET}    {result['years']}")
            if "columns" in result:
                print(f"  {c.GRAY}Columns:{c.RESET}  {', '.join(result['columns'][:5])}...")
            if "indicators" in result:
                print()
                print(f"  {c.BOLD}Matching Indicators:{c.RESET}")
                for ind in result['indicators'][:10]:
                    print(f"    {c.CYAN}{ind['code']:25}{c.RESET} {ind['name'][:50]}")
                if len(result['indicators']) > 10:
                    print(f"    {c.GRAY}... and {len(result['indicators']) - 10} more{c.RESET}")
            print()
            return 0
        else:
            print(f"  {c.RED}✗{c.RESET} {result.get('message', 'Unknown error')}\n")
            return 1

    except Exception as e:
        print_friendly_error(e)
        return 1


def main():
    """Main CLI entry point."""
    import argparse

    apply_saved_runtime_config()

    # Handle subcommands before argparse (they have their own parsers)
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == 'tldr':
            return run_tldr_command(sys.argv[2:])
        if cmd == 'digest':
            return run_digest_command(sys.argv[2:])
        if cmd == 'revise':
            return run_revise_command(sys.argv[2:])
        if cmd == 'data':
            return run_data_command(sys.argv[2:])

    parser = argparse.ArgumentParser(
        prog="opendraft",
        description="AI-Powered Research Paper Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}Usage:{Colors.RESET}
  opendraft                    Interactive mode (recommended)
  opendraft setup              Configure API key + verify installation
  opendraft verify             Check system dependencies (PDF, LaTeX)
  opendraft "Your Topic"       Quick generate
  opendraft tldr <file>        Generate 5-bullet TL;DR for any paper
  opendraft digest <file>      Generate 60-second audio digest
  opendraft revise <folder> "instructions"   Revise existing draft
  opendraft data <provider> <query>          Fetch research datasets

{Colors.BOLD}Examples:{Colors.RESET}
  opendraft "Impact of AI on Education"
  opendraft "Climate Change" --level phd --lang de
  opendraft tldr paper.pdf
  opendraft digest paper.pdf --voice josh
  opendraft "Neural Networks" --expose              Quick research overview
  opendraft revise ./output "make the intro longer"
  opendraft data worldbank NY.GDP.MKTP.CD --countries USA;DEU

{Colors.BOLD}Languages:{Colors.RESET}
  en, de, es, fr, it, pt, nl, zh, ja, ko, ru, ar

{Colors.GRAY}https://opendraft.xyz{Colors.RESET}
        """
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"opendraft {__version__}"
    )

    parser.add_argument(
        "topic",
        nargs="?",
        help="Research topic (or 'setup')"
    )

    parser.add_argument(
        "--level", "-l",
        choices=["research_paper", "bachelor", "master", "phd"],
        default="research_paper",
        help="Academic level"
    )

    parser.add_argument(
        "--style", "-s",
        choices=["apa", "ieee", "chicago", "mla", "nalt"],
        default="apa",
        help="Citation style (apa, ieee, chicago, mla, nalt)"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )

    parser.add_argument(
        "--blurb", "-b",
        type=str,
        help="Research focus/context (optional)"
    )

    parser.add_argument(
        "--lang",
        type=str,
        default="en",
        help="Language code (en, de, es, fr, etc.)"
    )

    # Optional cover page metadata
    parser.add_argument(
        "--author",
        type=str,
        help="Author name for cover page"
    )

    parser.add_argument(
        "--institution",
        type=str,
        help="Institution/university name"
    )

    parser.add_argument(
        "--department",
        type=str,
        help="Department name"
    )

    parser.add_argument(
        "--advisor",
        type=str,
        help="Advisor/supervisor name"
    )

    parser.add_argument(
        "--expose",
        action="store_true",
        help="Generate research exposé only (faster, no full draft)"
    )

    parser.add_argument(
        "--resume",
        type=Path,
        help="Resume from checkpoint (path to checkpoint.json or output directory)"
    )

    args = parser.parse_args()
    c = Colors

    apply_saved_runtime_config()

    # Handle 'setup' command
    if args.topic and args.topic.lower() == 'setup':
        if run_setup():
            print()
            print(f"  {c.BOLD}Verifying installation...{c.RESET}")
            print()
            from opendraft.verify import verify_installation
            return verify_installation()
        return 1

    # Handle 'verify' command
    if args.topic and args.topic.lower() == 'verify':
        from opendraft.verify import verify_installation
        return verify_installation()


    # Interactive mode
    if not args.topic:
        return run_interactive()

    # Quick mode
    clear_screen()
    print_header()

    apply_saved_runtime_config()

    if not has_api_key():
        print(f"  {c.YELLOW}!{c.RESET} Run {c.BOLD}opendraft setup{c.RESET} first.\n")
        return 1

    if not os.getenv('GOOGLE_API_KEY'):
        os.environ['GOOGLE_API_KEY'] = get_api_key()

    # Language display names for quick mode
    quick_lang_names = {
        'en': 'English', 'de': 'German', 'es': 'Spanish', 'fr': 'French',
        'it': 'Italian', 'pt': 'Portuguese', 'nl': 'Dutch', 'zh': 'Chinese',
        'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian', 'ar': 'Arabic'
    }

    print(f"  {c.GRAY}Topic{c.RESET}  {args.topic}")
    if args.blurb:
        print(f"  {c.GRAY}Focus{c.RESET}  {args.blurb[:50]}{'...' if len(args.blurb) > 50 else ''}")
    print(f"  {c.GRAY}Level{c.RESET}  {args.level}")
    print(f"  {c.GRAY}Style{c.RESET}  {args.style.upper()}")
    print(f"  {c.GRAY}Language{c.RESET}  {quick_lang_names.get(args.lang, args.lang)}")
    if args.expose:
        print(f"  {c.GRAY}Mode{c.RESET}   {c.GREEN}Research Exposé{c.RESET} (faster)")
    if args.author:
        print(f"  {c.GRAY}Author{c.RESET}  {args.author}")
    if args.institution:
        print(f"  {c.GRAY}Institution{c.RESET}  {args.institution}")
    print()
    print_divider()
    print()
    if args.expose:
        print(f"  {c.PURPLE}⣾{c.RESET} {c.BOLD}Starting research exposé...{c.RESET}")
    else:
        print(f"  {c.PURPLE}⣾{c.RESET} {c.BOLD}Starting paper generation...{c.RESET}")
    print(f"  {c.GRAY}Loading AI modules...{c.RESET}", end='', flush=True)

    try:
        from draft_generator import generate_draft
        from utils.logging_config import enable_cli_mode
        print(f" {c.GREEN}✓{c.RESET}")

        # Enable user-friendly logging (hide timestamps, module names)
        enable_cli_mode()
        # NOTE: We keep research verbosity ON so users can see outline, sources, and progress

        print()
        print(f"  {c.CYAN}{'━' * 50}{c.RESET}")
        print(f"  {c.BOLD}🚀 Starting research on:{c.RESET} {args.topic[:50]}{'...' if len(args.topic) > 50 else ''}")
        print(f"  {c.CYAN}{'━' * 50}{c.RESET}")
        print()
        if args.expose:
            print(f"  {c.GRAY}Generating research exposé (2-5 minutes)...{c.RESET}")
        else:
            print(f"  {c.GRAY}This typically takes 10-15 minutes.{c.RESET}")
        print(f"  {c.GRAY}You'll see progress updates below.{c.RESET}")
        print()

        output_dir = args.output or Path.cwd() / 'opendraft_output'
        output_type = 'expose' if args.expose else 'full'

        # Handle resume from checkpoint
        resume_from = None
        if args.resume:
            resume_path = Path(args.resume)
            if resume_path.is_dir():
                resume_from = resume_path / "checkpoint.json"
            else:
                resume_from = resume_path
            if resume_from.exists():
                print(f"  {c.CYAN}Resuming from checkpoint...{c.RESET}")
                # Use output_dir from checkpoint location
                output_dir = resume_from.parent
            else:
                print(f"  {c.YELLOW}!{c.RESET} Checkpoint not found: {resume_from}")
                resume_from = None

        pdf_path, docx_path = generate_draft(
            topic=args.topic,
            language=args.lang,
            academic_level=args.level,
            output_dir=output_dir,
            skip_validation=True,
            verbose=True,
            blurb=args.blurb if args.blurb else None,
            output_type=output_type,
            author_name=args.author,
            institution=args.institution,
            department=args.department,
            advisor=args.advisor,
            citation_style=args.style,
            resume_from=resume_from,
        )

        print()
        print(f"  {c.GREEN}✓{c.RESET} {c.BOLD}Done{c.RESET}")
        print(f"  {c.GRAY}PDF{c.RESET}   {pdf_path}")
        print(f"  {c.GRAY}Word{c.RESET}  {docx_path}")
        print()
        return 0

    except KeyboardInterrupt:
        print(f"\n\n  {c.YELLOW}!{c.RESET} Interrupted.\n")
        return 1
    except Exception as e:
        print_friendly_error(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

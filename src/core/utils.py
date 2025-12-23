"""Core utility functions for the application."""

import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.core.config import AppConfig


def check_battery_status() -> int | None:
    """
    Checks the battery status on macOS using pmset.

    Returns:
        Battery percentage (int) or None if not on macOS or error occurs.
    """
    if sys.platform != "darwin":
        return None  # Only works on macOS

    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            check=True,
            close_fds=False,
            timeout=10,  # Add timeout for security
        )
        output_lines = result.stdout.split("\n")
        for line in output_lines:
            if "InternalBattery" in line:
                match = re.search(r"(\d+)%", line)
                if match:
                    return int(match.group(1))
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logging.warning(f"Could not retrieve battery status: {e}")
    return None


def get_battery_status() -> dict[str, int | bool] | None:
    """
    Get detailed battery status on macOS using pmset.

    Returns:
        dict with 'percent' (int) and 'plugged' (bool), or None if not on macOS or error occurs.
    """
    if sys.platform != "darwin":
        return None  # Only works on macOS

    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            check=True,
            close_fds=False,
            timeout=10,  # Add timeout for security
        )
        output = result.stdout

        # Extract percentage
        percent_match = re.search(r"(\d+)%", output)
        percent = int(percent_match.group(1)) if percent_match else 100

        # Check if AC power is connected
        plugged = "AC Power" in output or "discharging" not in output.lower()

        return {"percent": percent, "plugged": plugged}
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logging.warning(f"Could not retrieve battery status: {e}")
    return None


def pause_on_low_battery(config: AppConfig | None = None) -> None:
    """
    Pauses script execution if battery is below configured threshold and resumes when above high threshold.
    Checks battery every minute while paused.

    Args:
        config: Application configuration instance (optional, creates default if None)
    """
    if sys.platform != "darwin":
        return  # Only relevant for macOS

    # Use provided config or create default if None
    if config is None:
        config = AppConfig()

    low_threshold = config.BATTERY_LOW_THRESHOLD
    high_threshold = config.BATTERY_HIGH_THRESHOLD
    check_interval_seconds = config.BATTERY_CHECK_INTERVAL

    while True:
        battery_percent = check_battery_status()
        if battery_percent is None:
            logging.warning("Battery status unavailable. Cannot pause based on charge. Continuing.")
            return  # Can't get status, so don't pause

        if battery_percent < low_threshold:
            logging.warning(f"Battery charge is {battery_percent}% (below {low_threshold}%). Pausing processing.")
            logging.info(f"Script will resume when battery is above {high_threshold}%.")
            while battery_percent < high_threshold:
                logging.info(f"  (Paused) Current battery: {battery_percent}%. Checking again in {check_interval_seconds} seconds.")
                time.sleep(check_interval_seconds)
                battery_percent = check_battery_status()
                if battery_percent is None:
                    logging.warning("Battery status became unavailable while paused. Resuming processing, but be aware of battery levels.")
                    return  # If status becomes unavailable, resume rather than getting stuck
            logging.info(f"Battery charged to {battery_percent}% (above {high_threshold}%). Resuming processing.")
        else:
            return  # Battery is OK, continue processing


def get_repo_urls_from_file(repos_txt_path: str = "repos.txt") -> list[str]:
    """
    Get repository URLs from a text file.

    Args:
        repos_txt_path: Path to the repositories text file

    Returns:
        List of repository URLs
    """
    urls = []
    try:
        # Validate path to prevent directory traversal
        safe_path = Path(repos_txt_path).resolve()
        current_dir = Path.cwd().resolve()
        temp_dirs = [Path("/tmp"), Path("/var/folders"), Path("/private/var/folders")]  # Common temp dirs

        # Allow files in current directory or standard temp directories (for testing)
        is_temp_dir = any(safe_path.is_relative_to(temp_dir) for temp_dir in temp_dirs)
        is_current_dir = safe_path.is_relative_to(current_dir)

        if not (is_current_dir or is_temp_dir):
            logging.error(f"Path {repos_txt_path} is outside current directory and temp dirs. Security risk.")
            return urls

        with open(safe_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        logging.error(f"{repos_txt_path} not found.")
    except Exception as e:
        logging.error(f"Error reading {repos_txt_path}: {e}")
    return urls


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    Uses a rough approximation (4 characters per token for English text).

    Args:
        text: Input text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    return len(text) // 4


def calculate_dynamic_timeout(file_path: str, base_timeout: int = 300, min_timeout: int = 30, max_timeout: int = 3600) -> int:
    """
    Calculate a dynamic timeout based on file size.

    Args:
        file_path: Path to the file
        base_timeout: Base timeout in seconds for a reference file size
        min_timeout: Minimum timeout to use
        max_timeout: Maximum timeout to use

    Returns:
        Calculated timeout in seconds
    """
    try:
        file_size = os.path.getsize(file_path)
        # Base timeout for a 1MB file, scale linearly
        reference_size = 1024 * 1024  # 1MB in bytes
        scaling_factor = file_size / reference_size

        # Apply a square root scaling to prevent extremely large timeouts for huge files
        # This means a 4x larger file gets 2x timeout, not 4x timeout
        adjusted_timeout = base_timeout * (scaling_factor**0.5)

        # Clamp to min/max bounds
        return int(max(min_timeout, min(adjusted_timeout, max_timeout)))
    except (OSError, TypeError):
        # If we can't determine file size, return base timeout
        return base_timeout


def smart_split_code(content: str, max_context_tokens: int, overlap_ratio: float = 0.2) -> list[str]:
    """
    Split code into chunks that respect logical boundaries while staying within token limits.

    Args:
        content: Full content to split
        max_context_tokens: Maximum tokens per chunk
        overlap_ratio: Ratio of overlap between chunks to maintain context

    Returns:
        List of code chunks
    """
    if estimate_tokens(content) <= max_context_tokens:
        return [content]

    lines = content.split("\n")
    chunks = []
    current_chunk = []
    current_token_count = 0

    max_chunk_tokens = int(max_context_tokens * (1 - overlap_ratio))  # Account for overlap

    i = 0
    while i < len(lines):
        line = lines[i]
        line_tokens = estimate_tokens(line)

        # If adding this line would exceed the limit, finalize current chunk
        if current_token_count + line_tokens > max_chunk_tokens and current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunks.append(chunk_content)

            # Add overlap if needed
            overlap_size = int(len(current_chunk) * overlap_ratio)
            if overlap_size > 0:
                current_chunk = current_chunk[-overlap_size:]
                current_token_count = estimate_tokens("\n".join(current_chunk))
            else:
                current_chunk = []
                current_token_count = 0
        else:
            current_chunk.append(line)
            current_token_count += line_tokens
            i += 1

    # Add the final chunk if it has content
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def identify_key_sections(content: str, section_types: list[str] = None) -> list[str]:
    """
    Identify the most valuable sections of code for QA generation.

    Args:
        content: Full code content
        section_types: Types of sections to identify (functions, classes, etc.)

    Returns:
        List of important code sections
    """
    if section_types is None:
        section_types = ["def ", "function", "class ", "if ", "for ", "while ", "# "]

    lines = content.split("\n")
    sections = []
    current_section = []

    for line in lines:
        # Check if this line starts a new section of interest
        is_key_line = any(keyword in line.lower() for keyword in section_types)

        if is_key_line:
            # If we have a previous section, save it
            if current_section:
                sections.append("\n".join(current_section))

            # Get surrounding context
            section_start_idx = max(0, lines.index(line) - 3)
            section_end_idx = min(len(lines), lines.index(line) + 15)

            current_section = lines[section_start_idx:section_end_idx]
        elif current_section and not line.strip():
            # If we're in a section and hit empty line, consider ending it
            if len([line_content for line_content in current_section if line_content.strip()]) > 10:  # If section is substantial
                sections.append("\n".join(current_section))
                current_section = []

    # Add final section if it exists
    if current_section:
        sections.append("\n".join(current_section))

    return sections


def _scrape_h3_repos(soup) -> list[str]:
    """Scrape repositories from h3 tags with wb-break-all class."""
    repos = []
    for h3_tag in soup.find_all("h3", class_="wb-break-all"):
        a_tag = h3_tag.find("a")
        if a_tag and a_tag.get("href"):
            href = a_tag.get("href")
            if href and href.startswith("/"):
                repos.append(f"https://github.com{href}")
    return repos


def _scrape_hovercard_repos(soup) -> list[str]:
    """Scrape repositories from links with data-hovercard-type attribute."""
    repos = []
    for a_tag in soup.find_all("a", {"data-hovercard-type": "repository"}):
        href = a_tag.get("href")
        if href and href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def _scrape_boxrow_repos(soup) -> list[str]:
    """Scrape repositories from Box-row divs with itemprop attribute."""
    repos = []
    for div_tag in soup.find_all("div", class_="Box-row"):
        a_tag = div_tag.find("a", {"itemprop": "name codeRepository"})
        if a_tag:
            href = a_tag.get("href")
            if href and href.startswith("/"):
                repos.append(f"https://github.com{href}")
    return repos


def _scrape_valign_repos(soup) -> list[str]:
    """Scrape repositories from v-align-middle links."""
    repos = []
    for a_tag in soup.find_all("a", class_="v-align-middle"):
        href = a_tag.get("href")
        # e.g., /owner/repo format
        if href and href.count("/") == 2 and href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def get_repos_from_github_page(org_url: str) -> list[str]:
    """
    Scrape repositories from a GitHub organization or user page.

    Uses multiple scraping strategies to find repository links.

    Args:
        org_url: GitHub organization or user page URL

    Returns:
        List of unique repository URLs
    """
    # Validate URL to prevent SSRF attacks
    if not org_url.startswith(("http://", "https://")) or "github.com" not in org_url:
        logging.error(f"Invalid GitHub URL: {org_url}")
        return []

    logging.info(f"Attempting to scrape repositories from GitHub page: {org_url}")
    repo_links = set()

    try:
        headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3")}
        # Add timeout to prevent hanging requests
        response = requests.get(org_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Apply all scraping strategies
        repo_links.update(_scrape_h3_repos(soup))
        repo_links.update(_scrape_hovercard_repos(soup))
        repo_links.update(_scrape_boxrow_repos(soup))
        repo_links.update(_scrape_valign_repos(soup))

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {org_url}: {e}")
    except Exception as e:
        logging.error(f"Error parsing GitHub page {org_url}: {e}")

    time.sleep(1)  # Rate limiting
    return list(repo_links)


def _run_git_command(cmd: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """
    Run a git command synchronously using subprocess.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory for the command

    Returns:
        tuple: (success: bool, output/error: str)
    """
    # Validate command to prevent command injection
    if not cmd or not isinstance(cmd, list):
        return (False, "Invalid command format")

    # Ensure all command elements are strings and don't contain dangerous characters
    for item in cmd:
        if not isinstance(item, str):
            return (False, f"Command contains non-string element: {item}")
        if any(char in item for char in ["&", "|", ";", "$", "`"]):
            return (False, f"Command contains potentially dangerous characters: {item}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            cwd=cwd,
            text=True,
            check=False,
            close_fds=False,
            timeout=300,  # 5 minute timeout for security
        )

        if result.returncode == 0:
            return (True, result.stdout)
        else:
            return (False, result.stderr)
    except subprocess.TimeoutExpired:
        return (False, "Git command timed out after 5 minutes")
    except Exception as e:
        return (False, str(e))


def clone_or_update_repos(repos_dir: str, repo_urls: list[str], progress_callback=None) -> None:
    """
    Clone or update repositories synchronously with progress reporting.

    Args:
        repos_dir: Directory to store repositories
        repo_urls: List of repository URLs to clone/update
        progress_callback: Optional callback to report progress (received_url, status, index, total)
    """
    # Validate repos_dir to prevent directory traversal
    try:
        repos_path = Path(repos_dir).resolve()
        current_dir = Path.cwd().resolve()
        temp_dirs = [Path("/tmp"), Path("/var/folders"), Path("/private/var/folders")]  # Common temp dirs

        # Allow repos in current directory or standard temp directories (for testing)
        is_temp_dir = any(repos_path.is_relative_to(temp_dir) for temp_dir in temp_dirs)
        is_current_dir = repos_path.is_relative_to(current_dir)

        if not (is_current_dir or is_temp_dir):
            logging.error(f"Repository directory {repos_dir} is outside current directory and temp dirs. Security risk.")
            return
    except Exception:
        logging.error(f"Invalid repository directory path: {repos_dir}")
        return

    # Validate URLs to prevent command injection
    validated_urls = []
    for url in repo_urls:
        if not url.startswith(("https://", "http://", "git@")) or not url.strip():
            logging.warning(f"Skipping invalid URL: {url}")
            continue
        validated_urls.append(url)

    total_repos = len(validated_urls)
    for index, url in enumerate(validated_urls, 1):
        parsed_url = urlparse(url)

        repo_name_from_url = url.split("/")[-1].replace(".git", "")

        # Sanitize the repo name to prevent path traversal
        repo_name_from_url = os.path.basename(repo_name_from_url)
        final_repo_path = os.path.join(repos_dir, repo_name_from_url)

        if "github.com" in parsed_url.netloc:
            path_segments = [s for s in parsed_url.path.split("/") if s]

            if len(path_segments) >= 2:
                owner_name = path_segments[0]
                repo_name = path_segments[1].replace(".git", "")

                # Sanitize owner and repo names to prevent path traversal
                owner_name = os.path.basename(owner_name)
                repo_name = os.path.basename(repo_name)

                owner_dir = os.path.join(repos_dir, owner_name)
                os.makedirs(owner_dir, exist_ok=True)

                final_repo_path = os.path.join(owner_dir, repo_name)
                logging.info(f"Organizing {repo_name_from_url} under owner '{owner_name}'.")
            else:
                logging.info(f"Could not determine owner for GitHub URL: {url}. Cloning directly under 'repos/'.")

        # Report progress for repo start
        if progress_callback:
            progress_callback(url, "starting", index, total_repos)

        if os.path.exists(final_repo_path):
            if progress_callback:
                progress_callback(url, "updating", index, total_repos)

            logging.info(f"Updating existing repository: {repo_name_from_url} at {final_repo_path}")
            # Discard any local changes
            success, output = _run_git_command(["git", "reset", "--hard", "HEAD"], cwd=final_repo_path)
            if not success:
                logging.error(f"Error resetting {repo_name_from_url}: {output}")
                if progress_callback:
                    progress_callback(url, "error", index, total_repos)
                continue  # Skip to next repo if reset fails

            # Git pull
            success, output = _run_git_command(["git", "pull"], cwd=final_repo_path)
            if success:
                logging.debug(f"Successfully updated {repo_name_from_url}")
                if progress_callback:
                    progress_callback(url, "updated", index, total_repos)
            else:
                logging.error(f"Error updating {repo_name_from_url}: {output}")
                if progress_callback:
                    progress_callback(url, "error", index, total_repos)
        else:
            if progress_callback:
                progress_callback(url, "cloning", index, total_repos)

            logging.info(f"Cloning new repository: {repo_name_from_url} into {final_repo_path}")
            # Git clone
            success, output = _run_git_command(["git", "clone", url, final_repo_path])
            if success:
                logging.debug(f"Successfully cloned {repo_name_from_url}")
                if progress_callback:
                    progress_callback(url, "cloned", index, total_repos)
            else:
                logging.error(f"Error cloning {repo_name_from_url}: {output}")
                if progress_callback:
                    progress_callback(url, "error", index, total_repos)

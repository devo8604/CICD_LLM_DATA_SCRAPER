import os
import sys
import json
import git
import re
import requests
import time
import asyncio
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
from tqdm import tqdm
import subprocess

from src.config import AppConfig

# Initialize config instance
config = AppConfig()


def check_battery_status():
    """
    Checks the battery status on macOS using pmset.
    Returns battery percentage (int) or None if not on macOS or error occurs.
    """
    if sys.platform != "darwin":
        return None  # Only works on macOS

    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, check=True
        )
        output_lines = result.stdout.split("\n")
        for line in output_lines:
            if "InternalBattery" in line:
                match = re.search(r"(\d+)%", line)
                if match:
                    return int(match.group(1))
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        ValueError,
        TypeError,
        AttributeError,
    ) as e:
        logging.warning(f"Could not retrieve battery status: {e}")
    return None


def pause_on_low_battery():
    """
    Pauses script execution if battery is below configured threshold and resumes when above high threshold.
    Checks battery every minute while paused.
    """
    if sys.platform != "darwin":
        return  # Only relevant for macOS

    low_threshold = config.BATTERY_LOW_THRESHOLD
    high_threshold = config.BATTERY_HIGH_THRESHOLD
    check_interval_seconds = config.BATTERY_CHECK_INTERVAL

    while True:
        battery_percent = check_battery_status()
        if battery_percent is None:
            logging.warning(
                "Battery status unavailable. Cannot pause based on charge. Continuing."
            )
            return  # Can't get status, so don't pause

        if battery_percent < low_threshold:
            logging.warning(
                f"Battery charge is {battery_percent}% (below {low_threshold}%). Pausing processing."
            )
            logging.info(f"Script will resume when battery is above {high_threshold}%.")
            while battery_percent < high_threshold:
                logging.info(
                    f"  (Paused) Current battery: {battery_percent}%. Checking again in {check_interval_seconds} seconds."
                )
                time.sleep(check_interval_seconds)
                battery_percent = check_battery_status()
                if battery_percent is None:
                    logging.warning(
                        "Battery status became unavailable while paused. Resuming processing, but be aware of battery levels."
                    )
                    return  # If status becomes unavailable, resume rather than getting stuck
            logging.info(
                f"Battery charged to {battery_percent}% (above {high_threshold}%). Resuming processing."
            )
        else:
            return  # Battery is OK, continue processing


def get_repo_urls_from_file(repos_txt_path="repos.txt"):
    urls = []
    try:
        with open(repos_txt_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        logging.error(f"{repos_txt_path} not found.")
    return urls


def _scrape_h3_repos(soup):
    """Scrape repositories from h3 tags with wb-break-all class."""
    repos = []
    for h3_tag in soup.find_all("h3", class_="wb-break-all"):
        a_tag = h3_tag.find("a")
        if a_tag and a_tag.get("href"):
            href = a_tag.get("href")
            if href and href.startswith("/"):
                repos.append(f"https://github.com{href}")
    return repos


def _scrape_hovercard_repos(soup):
    """Scrape repositories from links with data-hovercard-type attribute."""
    repos = []
    for a_tag in soup.find_all("a", {"data-hovercard-type": "repository"}):
        href = a_tag.get("href")
        if href and href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def _scrape_boxrow_repos(soup):
    """Scrape repositories from Box-row divs with itemprop attribute."""
    repos = []
    for div_tag in soup.find_all("div", class_="Box-row"):
        a_tag = div_tag.find("a", {"itemprop": "name codeRepository"})
        if a_tag:
            href = a_tag.get("href")
            if href and href.startswith("/"):
                repos.append(f"https://github.com{href}")
    return repos


def _scrape_valign_repos(soup):
    """Scrape repositories from v-align-middle links."""
    repos = []
    for a_tag in soup.find_all("a", class_="v-align-middle"):
        href = a_tag.get("href")
        # e.g., /owner/repo format
        if href and href.count("/") == 2 and href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def get_repos_from_github_page(org_url):
    """
    Scrape repositories from a GitHub organization or user page.

    Uses multiple scraping strategies to find repository links.

    Args:
        org_url: GitHub organization or user page URL

    Returns:
        List of unique repository URLs
    """
    logging.info(f"Attempting to scrape repositories from GitHub page: {org_url}")
    repo_links = set()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(org_url, headers=headers)
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


async def _run_git_command(cmd: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """
    Run a git command asynchronously using subprocess.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory for the command

    Returns:
        tuple: (success: bool, output/error: str)
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return (True, stdout.decode())
        else:
            return (False, stderr.decode())
    except Exception as e:
        return (False, str(e))


async def clone_or_update_repos(repos_dir: str, repo_urls: list[str]) -> None:
    """
    Clone or update repositories asynchronously.

    Args:
        repos_dir: Directory to store repositories
        repo_urls: List of repository URLs to clone/update
    """
    for url in repo_urls:
        parsed_url = urlparse(url)

        repo_name_from_url = url.split("/")[-1].replace(".git", "")

        final_repo_path = os.path.join(repos_dir, repo_name_from_url)

        if "github.com" in parsed_url.netloc:
            path_segments = [s for s in parsed_url.path.split("/") if s]

            if len(path_segments) >= 2:
                owner_name = path_segments[0]
                repo_name = path_segments[1].replace(".git", "")

                owner_dir = os.path.join(repos_dir, owner_name)
                os.makedirs(owner_dir, exist_ok=True)

                final_repo_path = os.path.join(owner_dir, repo_name)
                logging.info(
                    f"Organizing {repo_name_from_url} under owner '{owner_name}'."
                )
            else:
                logging.info(
                    f"Could not determine owner for GitHub URL: {url}. Cloning directly under 'repos/'."
                )

        if os.path.exists(final_repo_path):
            logging.info(
                f"Updating existing repository: {repo_name_from_url} at {final_repo_path}"
            )
            # Discard any local changes
            success, output = await _run_git_command(
                ["git", "reset", "--hard", "HEAD"],
                cwd=final_repo_path
            )
            if not success:
                logging.error(f"Error resetting {repo_name_from_url}: {output}")
                continue # Skip to next repo if reset fails

            # Async git pull
            success, output = await _run_git_command(
                ["git", "pull"],
                cwd=final_repo_path
            )
            if success:
                logging.debug(f"Successfully updated {repo_name_from_url}")
            else:
                logging.error(f"Error updating {repo_name_from_url}: {output}")
        else:
            logging.info(
                f"Cloning new repository: {repo_name_from_url} into {final_repo_path}"
            )
            # Async git clone
            success, output = await _run_git_command(
                ["git", "clone", url, final_repo_path]
            )
            if success:
                logging.debug(f"Successfully cloned {repo_name_from_url}")
            else:
                logging.error(f"Error cloning {repo_name_from_url}: {output}")

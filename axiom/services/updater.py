"""Native Git Update Manager.

Checks the GitHub repository API for new tags.
Performs a background 'git pull origin main' to synchronize local code changes
without a full binary reinstall.
"""
import logging
import asyncio
import subprocess
import urllib.request
import json
import os

logger = logging.getLogger(__name__)

class AxiomUpdateManager:
    """Manages OTA software updates via Git."""
    
    def __init__(self, current_version: str = "v6.0.0"):
        self.current_version = current_version
        self.repo_api_url = "https://api.github.com/repos/Rutytoi220/Axiom/releases/latest"
        
    async def check_for_updates(self) -> dict:
        """Checks GitHub API for the latest release tag."""
        logger.info("AxiomUpdateManager: Checking for updates...")
        
        def _fetch():
            try:
                req = urllib.request.Request(self.repo_api_url, headers={'User-Agent': 'Axiom-Updater'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    return data.get("tag_name", self.current_version)
            except Exception as e:
                logger.error(f"AxiomUpdateManager: Failed to fetch updates - {e}")
                return self.current_version

        latest_version = await asyncio.to_thread(_fetch)
        
        # Simple semantic version check (e.g. 'v6.1.0' > 'v6.0.0')
        update_available = latest_version != self.current_version and latest_version > self.current_version
        
        if update_available:
            logger.info(f"AxiomUpdateManager: New update available! {self.current_version} -> {latest_version}")
        else:
            logger.info("AxiomUpdateManager: System is up to date.")
            
        return {
            "update_available": update_available,
            "latest_version": latest_version,
            "current_version": self.current_version
        }

    async def perform_update(self, mock_mode: bool = False) -> bool:
        """Executes 'git pull origin main' to sync changes."""
        logger.info("AxiomUpdateManager: Initiating Over-The-Air Git Update...")
        
        def _pull():
            if mock_mode:
                logger.info("AxiomUpdateManager: [MOCK] Executing 'git pull origin main'")
                return True
                
            try:
                # We assume the user is running AXIOM from a git repository
                if not os.path.exists(".git"):
                    logger.error("AxiomUpdateManager: Not a git repository. Cannot perform OTA update.")
                    return False
                    
                result = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    logger.info(f"AxiomUpdateManager: Update successful.\n{result.stdout}")
                    return True
                else:
                    logger.error(f"AxiomUpdateManager: Update failed.\n{result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"AxiomUpdateManager: Exception during update - {e}")
                return False

        success = await asyncio.to_thread(_pull)
        return success

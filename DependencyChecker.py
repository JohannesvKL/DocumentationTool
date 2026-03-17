import subprocess
import os
import getpass
import re
import json
import argparse
import sys
import shutil
from pathlib import Path
from FileFunctions import check_conda_file, gitgetter, fetch_github_file


def check_dependencies_for_repo_with_local_files(repo_dir, dockerfiles, conda_files):
    """Check dependency pinning using already downloaded files"""
    dependency_lines = []
    dependency_lines.append(f"Checking dependencies for repository: {repo_dir}")
    
    # Check for conda environment files
    unpinned_found = False
    pinned_found = False
    
    for conda_file in conda_files:
        unpinned = check_conda_file(conda_file)
        if unpinned:
            unpinned_found = True
            dependency_lines.append(f"⚠️  Found unpinned dependencies in {conda_file}:")
            for dep in unpinned:
                dependency_lines.append(f"  - {dep}")
        else:
            pinned_found = True
    
    if not conda_files:
        dependency_lines.append("No conda environment files found in repository")
    
    return '\n'.join(dependency_lines)

def check_dependencies_for_repo(repo_url):
    """Check dependency pinning for a GitHub repository"""
    dependency_lines = []
    dependency_lines.append(f"Checking dependencies for repository: {repo_url}")
    
    # Use the absolute path to find the files
    dockerfiles, conda_files, repo_dir = gitgetter(repo_url)

    unpinned_found = False
    pinned_found = False
    for conda_file in conda_files:
            unpinned = check_conda_file(conda_file)
            if unpinned:
                unpinned_found = True
                dependency_lines.append(f"⚠️  Found unpinned dependencies in {conda_file}:")
                for dep in unpinned:
                    dependency_lines.append(f"  - {dep}")
            else:
                #dependency_lines.append(f"✅ All {conda_file} dependencies appear to be pinned!")
                pinned_found = True 
        
            #break  # Only check the first conda file found

    if os.path.exists(repo_dir):
                print(f"Cleaning up {repo_dir}...")
                shutil.rmtree(repo_dir)
                print("Cleanup complete.")
    
    return '\n'.join(dependency_lines)
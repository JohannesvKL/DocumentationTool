import os
import re
import git 
import shutil
import git 
import requests
import yaml
import json 

def find_files(directory):
    """Finds Dockerfiles and conda environment files."""
    dockerfiles = []
    conda_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower() == 'dockerfile':
                dockerfiles.append(os.path.join(root, file))
            if file.lower().endswith(('.yml', '.yaml')) and 'conda' in open(os.path.join(root, file)).read().lower():
                # A simple check to see if it's a conda file
                conda_files.append(os.path.join(root, file))
    return dockerfiles, conda_files

def find_files_robust(directory):
    """Finds Dockerfiles and conda environment files."""
    dockerfiles = []
    conda_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)

            # Check for Dockerfiles
            if file.lower() == 'dockerfile':
                dockerfiles.append(file_path)

            # Check for conda environment files
            elif file.lower().endswith(('.yml', '.yaml')):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Attempt to load as YAML
                        data = yaml.safe_load(f)
                        # A valid conda environment file will have a 'dependencies' key
                        if isinstance(data, dict) and 'dependencies' in data:
                            conda_files.append(file_path)
                except Exception as e:
                    # Ignore files that aren't valid YAML or cause other read errors
                    print(f"Skipping {file_path} due to error: {e}")

    return dockerfiles, conda_files

def check_dockerfile(filepath):
    """Parses a Dockerfile to find unpinned dependencies."""
    unpinned = []
    with open(filepath, 'r') as f:
        content = f.read()

    # Regex for apt-get
    apt_pattern = r'apt-get install(?: -y)?\s+((?:[a-zA-Z0-9-.]+\s*)+)'
    apt_matches = re.findall(apt_pattern, content)
    for match in apt_matches:
        packages = match.strip().split()
        for pkg in packages:
            if '=' not in pkg and not pkg.startswith('-'):
                unpinned.append(f"apt: {pkg}")

    # Regex for pip
    pip_pattern = r'pip install\s+((?:[a-zA-Z0-9-._\[\]]+\s*)+)'
    pip_matches = re.findall(pip_pattern, content)
    for match in pip_matches:
        packages = match.strip().split()
        for pkg in packages:
             # Ignores flags like --no-cache-dir and file paths
            if not any(c in pkg for c in '=<>~') and not pkg.startswith('-') and not '.' in pkg:
                unpinned.append(f"pip: {pkg}")

    return unpinned

def check_conda_file(filepath):
    """Parses a conda environment.yml file for unpinned dependencies using pyyaml."""
    unpinned = []
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)

    if 'dependencies' in data:
        for dep in data['dependencies']:
            # The dependency can be a string (e.g., 'python=3.9') or a dict
            if isinstance(dep, str):
                # Check for a package that does not have a version specifier
                # (e.g., '=', '==', '>', '<', '>=', '<=', '!=')
                if not any(char in dep for char in '=<>' '~'):
                    unpinned.append(f"conda: {dep}")
    return unpinned


def main_checker(pipeline_dir):
    """Main function to run the dependency check."""
    dockerfiles, conda_files = find_files(pipeline_dir)
    all_unpinned = {}

    print("--- Checking Dockerfiles ---")
    for df in dockerfiles:
        unpinned = check_dockerfile(df)
        if unpinned:
            all_unpinned[df] = unpinned
            print(f"Found unpinned dependencies in {df}:")
            for dep in unpinned:
                print(f"  - {dep}")

    print("\n--- Checking Conda Files ---")
    for cf in conda_files:
        unpinned = check_conda_file(cf)
        if unpinned:
            all_unpinned[cf] = unpinned
            print(f"Found unpinned dependencies in {cf}:")
            for dep in unpinned:
                print(f"  - {dep}")

    if not all_unpinned:
        print("\n✅ All dependencies appear to be pinned!")


def gitgetter(repo_url, name_suffix="2"): 
        repo_dir = f"temp_repo_for_analysis"
        dockerfiles = []
        conda_files = []
        try:
            # Step 1: Clone the repository
            print(f"Cloning repository from {repo_url}...")
            repo = git.Repo.clone_from(repo_url, repo_dir)
            print("Cloning successful. Beginning file search...")

            # Step 2: Run your analysis on the cloned directory
            dockerfiles, conda_files = find_files_robust(repo_dir)
            
            print(f"Found {len(dockerfiles)} Dockerfiles and {len(conda_files)} conda files.")

            # Optional: You can add your version checker functions here
            # for dockerfile in dockerfiles:
            #     unpinned_docker = check_dockerfile(dockerfile)
            #     if unpinned_docker:
            #         print(f"Dockerfile at {dockerfile} has unpinned dependencies: {unpinned_docker}")

            # for conda_file in conda_files:
            #     unpinned_conda = check_conda_file(conda_file)
            #     if unpinned_conda:
            #         print(f"Conda file at {conda_file} has unpinned dependencies: {unpinned_conda}")

        except git.exc.GitCommandError as e:
            print(f"Error cloning repository: {e}")

        return dockerfiles, conda_files, repo_dir

def fetch_github_file(repo_url, file_path, branch="main"):
    """Fetch a file from GitHub repository"""
    if "github.com" in repo_url:
        # Convert GitHub URL to raw content URL
        repo_url = repo_url.replace("github.com", "raw.githubusercontent.com")
        if not repo_url.endswith('/'):
            repo_url += '/'
        raw_url = f"{repo_url}{branch}/{file_path}"
    else:
        raw_url = repo_url
    
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        return f"Error fetching file: {e}"


def load_files_from_config(config_path):
    """Load files list from configuration file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check if config has a files list
        if "files" in config:
            return config["files"]
        elif "custom_files" in config:
            return config["custom_files"]
        else:
            print(f"Warning: No 'files' or 'custom_files' key found in {config_path}")
            return None
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return None
#gitgetter("https://github.com/nf-core/rnaseq")

# Example usage:
# main('/path/to/your/downloaded/pipeline')
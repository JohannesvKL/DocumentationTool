import os
import re
import shutil
import yaml
import json 

def find_files(directory):
    """Finds Dockerfiles and conda environment files."""
    dockerfiles = []
    conda_files = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__"}]
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
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__"}]
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
                    if file.lower() in {"environment.yml", "environment.yaml", "conda.yml", "conda.yaml"}:
                        raise ValueError(f"Invalid environment file {file_path}: {e}") from e

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
    """Return dependencies without an exact version, including nested pip entries."""
    with open(filepath, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or not isinstance(data.get("dependencies"), list):
        raise ValueError(f"Invalid Conda environment: {filepath}")
    unpinned = []
    for dep in data["dependencies"]:
        if isinstance(dep, str):
            # Conda name=version[=build]; ranges and wildcards are not exact pins.
            match = re.fullmatch(r"(?:[\w.-]+::)?[\w.-]+={1,2}([^=<>!~*,|\s]+)(?:=[\w.-]+)?", dep.strip())
            if not match:
                unpinned.append(f"conda: {dep}")
        elif isinstance(dep, dict) and set(dep) == {"pip"} and isinstance(dep['pip'], list):
            from packaging.requirements import Requirement, InvalidRequirement
            for req in dep['pip']:
                try:
                    parsed = Requirement(req)
                    specs = list(parsed.specifier)
                    pinned = len(specs) == 1 and specs[0].operator in {'==', '==='} and '*' not in specs[0].version
                except (InvalidRequirement, TypeError):
                    pinned = False
                if not pinned:
                    unpinned.append(f"pip: {req}")
        else:
            raise ValueError(f"Unsupported dependency entry in {filepath}: {dep!r}")
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


def gitgetter(repo_url, name_suffix=None):
    """Clone into an owned temporary directory and clean up if setup fails."""
    import git
    import tempfile
    repo_dir = tempfile.mkdtemp(prefix="documentation-check-")
    try:
        git.Repo.clone_from(repo_url, repo_dir)
        dockerfiles, conda_files = find_files_robust(repo_dir)
        return dockerfiles, conda_files, repo_dir
    except Exception:
        shutil.rmtree(repo_dir)
        raise


def fetch_github_file(repo_url, file_path, branch="main"):
    """Fetch a file from GitHub repository"""
    import requests
    if "github.com" in repo_url:
        # Convert GitHub URL to raw content URL
        repo_url = repo_url.replace("github.com", "raw.githubusercontent.com")
        if not repo_url.endswith('/'):
            repo_url += '/'
        raw_url = f"{repo_url}{branch}/{file_path}"
    else:
        raw_url = repo_url
    
    try:
        response = requests.get(raw_url, timeout=30)
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
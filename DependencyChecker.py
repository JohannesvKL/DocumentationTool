"""Structured evidence for Conda dependency pinning."""
from pathlib import Path
import yaml
from FileFunctions import check_conda_file, gitgetter


def inspect_dependencies(repo_dir, dockerfiles, conda_files):
    result = {"status": "NOT_CHECKED", "all_pinned": False,
              "unpinned_dependencies": [], "files_analyzed": [], "reasons": []}
    errors = []
    declarations = 0
    for filename in conda_files:
        try:
            unpinned = check_conda_file(filename)
            data = yaml.safe_load(Path(filename).read_text(encoding="utf-8"))
            declarations += sum(1 if isinstance(d, str) else len(d.get('pip', [])) for d in data['dependencies'])
            result['unpinned_dependencies'].extend(unpinned)
            result['files_analyzed'].append(str(Path(filename).relative_to(repo_dir)))
        except (OSError, ValueError, yaml.YAMLError) as e:
            errors.append(str(e))
    if errors:
        result['status'] = 'ERROR'
        result['reasons'].extend(errors)
    elif result['unpinned_dependencies']:
        result['status'] = 'FAIL'
        result['reasons'].extend(result['unpinned_dependencies'])
    elif declarations and not dockerfiles:
        result['status'] = 'PASS'
        result['all_pinned'] = True
        result['reasons'].append('All inspected Conda and nested pip declarations use exact versions.')
    if not declarations:
        result['reasons'].append('No Conda dependency declarations available to assess.')
    if dockerfiles:
        result['reasons'].append('Dockerfiles detected; Docker image and RUN dependency pinning are not assessed.')
    return result


def check_dependencies_for_repo_with_local_files(repo_dir, dockerfiles, conda_files):
    """Compatibility text interface; assessments consume inspect_dependencies instead."""
    result = inspect_dependencies(repo_dir, dockerfiles, conda_files)
    return result['status'] + ': ' + '\n'.join(result['reasons'])


def check_dependencies_for_repo(repo_url):
    import shutil
    dockerfiles, conda_files, repo_dir = gitgetter(repo_url)
    try:
        return check_dependencies_for_repo_with_local_files(repo_dir, dockerfiles, conda_files)
    finally:
        shutil.rmtree(repo_dir)

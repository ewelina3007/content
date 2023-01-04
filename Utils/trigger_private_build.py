import os
import re
import sys
import json
import time
import argparse
import requests
from typing import List
import demisto_sdk.commands.common.tools as tools
from Tests.scripts.utils.log_util import install_logging
from Tests.scripts.utils import logging_wrapper as logging

# disable insecure warnings
requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member


TRIGGER_BUILD_URL = 'https://api.github.com/repos/demisto/content-private/dispatches'
GET_DISPATCH_WORKFLOWS_URL = 'https://api.github.com/repos/demisto/content-private/actions/runs'
WORKFLOW_HTML_URL = 'https://github.com/demisto/content-private/actions/runs'
GET_WORKFLOW_URL = 'https://api.github.com/repos/demisto/content-private/actions/runs/{:s}/jobs'

PRIVATE_REPO_WORKFLOW_ID_FILE = 'PRIVATE_REPO_WORKFLOW_ID.txt'

GET_WORKFLOWS_MAX_RETRIES = 5

GET_WORKFLOWS_TIMEOUT_THRESHOLD = int(60 * 60 * 1.5)  # 1h 30m


def get_dispatch_workflows_ids(github_token: str, branch: str) -> List[int]:
    """ Gets private repo dispatch workflows on the given branch.

    Args:
        github_token: Github bearer token.
        branch: The branch to get the workflows from.

    Returns: A list of workflows ids.

    """
    res = requests.get(GET_DISPATCH_WORKFLOWS_URL,
                       headers={'Authorization': f'Bearer {github_token}'},
                       params={'branch': branch, 'event': 'repository_dispatch'},
                       verify=False)
    if res.status_code != 200:
        logging.error(f'Failed to get private repo workflows, request to '
                      f'{GET_DISPATCH_WORKFLOWS_URL} failed with error: {str(res.content)}')
        sys.exit(1)

    try:
        workflows = json.loads(res.content)
    except ValueError:
        logging.error('Enable to parse private repo workflows response')
        sys.exit(1)

    workflows = workflows.get('workflow_runs', [])
    return [workflow.get('id') for workflow in workflows]


def main():
    install_logging("TriggerPrivateBuild.log", logger=logging)
    # get github token parameter
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--github-token', help='Github token')
    args = arg_parser.parse_args()

    github_token = args.github_token

    # get branch name
    branches = tools.run_command("git branch")
    branch_name_regex = re.search(r"\* (.*)", branches)
    if branch_name_regex:
        branch_name = branch_name_regex.group(1)

    # get the workflows ids before triggering the build
    pre_existing_workflow_ids = get_dispatch_workflows_ids(github_token, 'master')

    # trigger private build
    payload = {'event_type': f'Trigger private build from content/{branch_name}',
               'client_payload': {'commit_sha1': branch_name, 'is_infra_build': 'True'}}

    res = requests.post(TRIGGER_BUILD_URL,
                        headers={'Accept': 'application/vnd.github.everest-preview+json',
                                 'Authorization': f'Bearer {github_token}'},
                        data=json.dumps(payload),
                        verify=False)

    if res.status_code != 204:
        logging.critical(f'Failed to trigger private repo build, request to '
                         f'{TRIGGER_BUILD_URL} failed with error: {str(res.content)}')
        sys.exit(1)

    workflow_ids_diff = []
    for i in range(GET_WORKFLOWS_MAX_RETRIES):
        # wait 5 seconds and get the workflow ids again
        time.sleep(5)
        workflow_ids_after_dispatch = get_dispatch_workflows_ids(github_token, 'master')

        # compare with the first workflows list to get the current id
        workflow_ids_diff = [x for x in workflow_ids_after_dispatch if x not in pre_existing_workflow_ids]
        if workflow_ids_diff:
            break

    if len(workflow_ids_diff) == 1:
        workflow_id = workflow_ids_diff[0]
        logging.success(f'Private repo build triggered successfully, workflow id: {workflow_id}\n URL:'
                        f' {WORKFLOW_HTML_URL}/{workflow_id}')

        # write the workflow id to text file to use it in get_private_build_status.py
        with open(PRIVATE_REPO_WORKFLOW_ID_FILE, "w") as f:
            f.write(str(workflow_id))
        sys.exit(0)

    else:
        logging.critical('Could not found the private repo workflow')
        sys.exit(1)


if __name__ == "__main__":
    main()

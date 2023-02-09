import pytest
import demistomock as demisto
import datetime
from CommonServerPython import IncidentStatus

from AWS_SecurityHub import AWSClient, get_findings_command, fetch_incidents, list_members_command

FILTER_FIELDS_TEST_CASES = [
    (
        'some non parseable input',
        {}
    ),
    (
        'name=name,value=value,comparison=comparison',
        {
            'name': [{
                'Value': 'value',
                'Comparison': 'COMPARISON'
            }]
        }
    ),
    (
        'name=name1,value=value1,comparison=comparison1;name=name2,value=value2,comparison=comparison2',
        {
            'name1': [{
                'Value': 'value1',
                'Comparison': 'COMPARISON1'
            }],
            'name2': [{
                'Value': 'value2',
                'Comparison': 'COMPARISON2'
            }]
        }
    )
]


@pytest.mark.parametrize('test_input, expected_output', FILTER_FIELDS_TEST_CASES)
def test_parse_filter_field(test_input, expected_output):
    """
    Given:
        - A string that represents filter fields with the structure 'name=...,value=...,comparison=...;name=...' etc.
    When:
     - Parsing it into a dict

    Then:
     - Ensure unparseable string returns an empty dict
     - Ensure one set of name,value,comparison is parsed correctly
     - Ensure two sets of name,value,comparison are parsed correctly
    """
    from AWS_SecurityHub import parse_filter_field
    assert parse_filter_field(test_input) == expected_output


TAG_FIELDS_TEST_CASES = [
    (
        'some non parseable input',
        []
    ),
    (
        'key=key,value=value',
        [{
            'Key': 'key',
            'Value': 'value'
        }]
    ),
    (
        'key=key1,value=value1;key=key2,value=value2',
        [
            {
                'Key': 'key1',
                'Value': 'value1'
            },
            {
                'Key': 'key2',
                'Value': 'value2'
            },
        ]
    )
]


@pytest.mark.parametrize('test_input, expected_output', TAG_FIELDS_TEST_CASES)
def test_parse_tag_field(test_input, expected_output):
    """
    Given:
        - A string that represents tag fields with the structure 'key=...,value=...;key=...,value...' etc.
    When:
     - Parsing it into a list of keys and values

    Then:
     - Ensure unparseable string returns an empty list
     - Ensure one pair of key, value is parsed correctly
     - Ensure two pairs of key, value are parsed correctly
    """
    from AWS_SecurityHub import parse_tag_field
    assert parse_tag_field(test_input) == expected_output


RESOURCE_IDS_TEST_CASES = [
    ('a,b,c', ['a', 'b', 'c']),
    ('a, b, c', ['a', 'b', 'c']),
    ('', [])
]


@pytest.mark.parametrize('test_input, expected_output', RESOURCE_IDS_TEST_CASES)
def test_parse_resource_ids(test_input, expected_output):
    """
    Given:
        - A string that represent a list of ids.
    When:
     - Parsing it into a list

    Then:
     - Ensure empty string returns an empty list
     - Ensure a string without spaces return a valid list separated by ','.
     - Ensure a string with spaces return a valid list separated by ','.
    """
    from AWS_SecurityHub import parse_resource_ids
    assert parse_resource_ids(test_input) == expected_output


FINDINGS = [{
    'ProductArn': 'Test',
    'Description': 'Test',
    'SchemaVersion': '2021-05-27',
    'CreatedAt': '2020-03-22T13:22:13.933Z',
    'UpdatedAt': '2023-02-01T14:01:59.833Z',
    'Id': 'Id',
    'Severity': {
        'Product': 0,
        'Label': 'INFORMATIONAL',
        'Normalized': 0,
        'Original': 'INFORMATIONAL'},
}]


class MockClient:

    def get_findings(self, **kwargs):
        return {'Findings': FINDINGS}

    def batch_update_findings(self, **kwargs):
        return {
            "ResponseMetadata": {
                "RequestId": "RequestId",
                "HTTPStatusCode": 200,
                "RetryAttempts": 0,
            },
            "ProcessedFindings": [{"Id": "ID", "ProductArn": "ProductArn"}],
            "UnprocessedFindings": [],
        }


def test_aws_securityhub_get_findings_command():
    """
    Given:
        - A dictionary that represents response body of aws_securityhub_get_findings API call without pagination -
        i.e doesn't have 'NextToken' key.
    When:
        - Running get_findings_command
    Then:
        - Verify returned value is as expected - i.e the findings list.
    """
    client = MockClient()
    human_readable, outputs, findings = get_findings_command(client, {})
    expected_output = FINDINGS

    assert findings == expected_output


def test_fetch_incidents(mocker):
    """
    Given:
        - A finding to fetch as incident with created time 2020-03-22T13:22:13.933Z
    When:
        - Fetching finding as incident
    Then:
        - Verify the last run is set as the created time + 1 millisecond, i.e. 2020-03-22T13:22:13.934Z
    """
    mocker.spy(demisto, 'setLastRun')
    client = MockClient()
    fetch_incidents(client, 'Low', False, None, 'Both', None, None, None)
    assert demisto.setLastRun.call_args[0][0]['lastRun'] == '2020-03-22T13:22:13.934000+00:00'


def test_list_members_command(mocker):
    """
    Given:
        - mock aws_session
    When:
        - Running list_members_command
    Then:
        - Ensure that the command was executed correctly. In particular, ensure that the datetime fields are convereted to str.
    """
    aws_client = AWSClient("reg", "", "", 900, "p", "mock_aws_access_key_id", "mock_aws_secret_access_key", "", "", 3)
    client = aws_client.aws_session(service='securityhub', region="reg", role_arn='roleArnroleArnroleArn',
                                    role_session_name='roleSessionName')
    time_val = datetime.datetime(2022, 1, 1, 12, 0, 0, 0)
    mock_response = {'ResponseMetadata': 'mock_ResponseMetadata',
                     'Members': [{'UpdatedAt': time_val, 'InvitedAt': time_val}]}
    mocker.patch.object(client, 'list_members', return_value=mock_response)
    _, _, response = list_members_command(client, {})
    time_val_iso_format = time_val.isoformat()
    assert response == {'Members': [{'UpdatedAt': time_val_iso_format, 'InvitedAt': time_val_iso_format}]}
    assert type(response['Members'][0]['UpdatedAt']) == str


severity_list = [('LOW', 1),
                 ('MEDIUM', 2),
                 ('HIGH', 3),
                 ('CRITICAL', 4),
                 ('INFORMATIONAL', 0)]


@pytest.mark.parametrize('severity, expected_demisto_severity', severity_list)
def test_severity_mapping(severity, expected_demisto_severity):
    """
        Given:
            - A string representing the incident severity, that returned from get_findings.
        When:
            - fetch_incidents command is running.
        Then:
            - Verifying demisto severity.
    """
    from AWS_SecurityHub import severity_mapping
    result = severity_mapping(severity)
    assert result == expected_demisto_severity


create_filters_list_dictionaries_params = [
    (
        ["TTPs", "Effects"],
        "PREFIX",
        [
            {"Comparison": "PREFIX", "Value": "TTPs"},
            {"Comparison": "PREFIX", "Value": "Effects"},
        ],
    ),
    (["New"], "EQUALS", [{"Comparison": "EQUALS", "Value": "New"}]),
]


@pytest.mark.parametrize('arr, compare_param, expected_result', create_filters_list_dictionaries_params)
def test_create_filters_list_dictionaries(arr, compare_param, expected_result):
    """
        Given:
            - A list of strings represents finding types or workflow statuses or product names and a
                comparison parameter.
        When:
            - fetch_incidents command is running.
        Then:
            - Checks the list of returned comparisons objects.
    """
    from AWS_SecurityHub import create_filters_list_dictionaries
    result = create_filters_list_dictionaries(arr, compare_param)
    assert result == expected_result


build_severity_label_obj_params = [
    (
        "Medium",
        [
            {"Comparison": "EQUALS", "Value": "MEDIUM"},
            {"Comparison": "EQUALS", "Value": "HIGH"},
            {"Comparison": "EQUALS", "Value": "CRITICAL"},
        ],
    ),
    ("Critical", [{"Comparison": "EQUALS", "Value": "CRITICAL"}]),
]


@pytest.mark.parametrize('label, expected_result', build_severity_label_obj_params)
def test_build_severity_label_obj(label, expected_result):
    """
        Given:
            - A severity label.
        When:
            - fetch_incidents command is running.
        Then:
            - Checks the returned  list of comparisons objects. For example, if the severity level is Medium, than the
                list of comparison object will contain MEDIUM, HIGH and CRITICAL.
    """
    from AWS_SecurityHub import build_severity_label_obj
    result = build_severity_label_obj(label)
    assert result == expected_result


def test_get_remote_data_command():
    """
    Given:
        - An incident id and the last update date
    When:
        - get_remote_data_command is executed
    Then:
        - Verifying the returned GetRemoteDataResponse object.
    """
    from AWS_SecurityHub import get_remote_data_command
    client = MockClient()
    args = {
        'id': 'Id',
        'lastUpdate': '2023-02-01T13:30:21.172707565Z'
    }
    result = get_remote_data_command(client, args)
    assert result.mirrored_object == FINDINGS[0]


def test_get_mapping_fields_command():
    """
    When:
        - get_mapping_fields_command is executed
    Then:
        - Verifying that a SchemeTypeMapping object containing the fields in the outgoing mapper is returned.
    """
    from AWS_SecurityHub import get_mapping_fields_command
    expected_fields = {
        'AWS Security Hub Finding': {
            'Confidence': '',
            'Criticality': '',
            'Note.Text': '',
            'Note.UpdatedBy': '',
            'Severity.Label': '',
            'VerificationState': '',
            'Workflow.Status': '',
            'FindingIdentifiers.Id': '',
            'FindingIdentifiers.ProductArn': ''
        }
    }
    result = get_mapping_fields_command()
    assert result.extract_mapping() == expected_fields


severity_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                             'FindingIdentifiers.ProductArn': 'ProductArn',
                             'Note.UpdatedBy': '',
                             'Severity.Label': 'LOW',
                             'Workflow.Status': 'NEW'},
                    'entries': [],
                    'remoteId': 'ID',
                    'status': IncidentStatus.ACTIVE,
                    'delta': {'Severity.Label': 'LOW'},
                    'incidentChanged': True}, 'ID',
                   {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                    'Severity': {'Label': 'LOW'}})

confidence_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                               'FindingIdentifiers.ProductArn': 'ProductArn',
                               'Note.UpdatedBy': '',
                               'Severity.Label': 'LOW',
                               'Workflow.Status': 'NEW',
                               'Confidence': 2},
                      'entries': [],
                      'remoteId': 'ID',
                      'status': IncidentStatus.ACTIVE,
                      'delta': {'Confidence': 1},
                      'incidentChanged': True}, 'ID',
                     {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                      'Confidence': 1})

criticality_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                                'FindingIdentifiers.ProductArn': 'ProductArn',
                                'Note.UpdatedBy': '',
                                'Severity.Label': 'LOW',
                                'Workflow.Status': 'NEW',
                                'Criticality': 10},
                       'entries': [],
                       'remoteId': 'ID',
                       'status': IncidentStatus.ACTIVE,
                       'delta': {'Criticality': 10},
                       'incidentChanged': True}, 'ID',
                      {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                       'Criticality': 10})

comment_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                            'FindingIdentifiers.ProductArn': 'ProductArn',
                            'Severity.Label': 'LOW',
                            'Workflow.Status': 'NEW',
                            'Note.Text': 'test',
                            'Note.UpdatedBy': 'admin'},
                   'entries': [],
                   'remoteId': 'ID',
                   'status': IncidentStatus.ACTIVE,
                   'delta': {'Note.Text': 'test'},
                   'incidentChanged': True}, 'ID',
                  {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                   'Note': {'Text': 'test', 'UpdatedBy': 'admin'}})

verification_state_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                                       'FindingIdentifiers.ProductArn': 'ProductArn',
                                       'Severity.Label': 'LOW',
                                       'Workflow.Status': 'NEW',
                                       'VerificationState': ['TRUE_POSITIVE'],
                                       'Note.UpdatedBy': 'admin'},
                              'entries': [],
                              'remoteId': 'ID',
                              'status': IncidentStatus.ACTIVE,
                              'delta': {'VerificationState': ['TRUE_POSITIVE']},
                              'incidentChanged': True}, 'ID',
                             {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                              'VerificationState': 'TRUE_POSITIVE'})

workflow_status_update = ({'data': {'FindingIdentifiers.Id': 'ID',
                                    'FindingIdentifiers.ProductArn': 'ProductArn',
                                    'Severity.Label': 'LOW',
                                    'Workflow.Status': 'NOTIFIED',
                                    'Note.UpdatedBy': 'admin'},
                           'entries': [],
                           'remoteId': 'ID',
                           'status': IncidentStatus.ACTIVE,
                           'delta': {'Workflow.Status': 'NOTIFIED'},
                           'incidentChanged': True}, 'ID',
                          {'FindingIdentifiers': [{'Id': 'ID', 'ProductArn': 'ProductArn'}],
                           'Workflow': {'Status': 'NOTIFIED'}})

test_update_remote_system_command_params = [severity_update,
                                            confidence_update,
                                            criticality_update,
                                            comment_update,
                                            verification_state_update,
                                            workflow_status_update]


@pytest.mark.parametrize('args, remote_id, expected_kwargs', test_update_remote_system_command_params)
def test_update_remote_system_command(mocker, args, remote_id, expected_kwargs):
    """
    Given:
        - A client and arguments that contain the incident data, entries, remote_incident_id, inc_status, delta,
            incident_changed.
    When:
        - update_remote_system_command is executed
    Then:
        - Verify that the correct arguments were sent to AWS Security Hub.
    """
    from AWS_SecurityHub import update_remote_system_command
    client = MockClient()
    batch_update_mock = mocker.patch.object(MockClient, 'batch_update_findings')
    result = update_remote_system_command(client, args)
    assert result == remote_id
    batch_update_mock.assert_called_with(**expected_kwargs)


def test_last_update_to_time():
    """
    Given:
        - A string representing a date and time.
    When:
        - get-remote-data is executed/
    Then:
        - Returns the timestamp.
    """
    from AWS_SecurityHub import last_update_to_time
    last_update = '2023-02-05T22:49:47.637Z'
    expected_timestamp = 1675637387
    result = last_update_to_time(last_update)
    assert result == expected_timestamp

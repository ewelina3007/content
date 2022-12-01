from enum import Enum
from typing import Dict, List
import demistomock as demisto
from CommonServerPython import *

special = ['n', 't', '\\', '"', '\'', '7', 'r']


class AlertSeverity(Enum):
    UNKNOWN = 0
    INFO = 0.5
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertStatus(Enum):
    PENDING = 0
    ACTIVE = 1
    DONE = 2
    ARCHIVE = 3


def check_if_found_incident(res: List):
    if res and isinstance(res, list) and isinstance(res[0].get('Contents'), dict):
        if 'data' not in res[0]['Contents']:
            raise DemistoException(res[0].get('Contents'))
        elif res[0]['Contents']['data'] is None:
            return False
        return True
    else:
        raise DemistoException(f'failed to get incidents from demisto.\nGot: {res}')


def is_valid_args(args: Dict):
    array_args: List[str] = ['id', 'name', 'status', 'notstatus', 'reason', 'level', 'owner', 'type', 'query']
    error_msg: List[str] = []
    for _key, value in args.items():
        if _key in array_args:
            try:
                if _key == 'id':
                    if not isinstance(value, (int, str, list)):
                        error_msg.append(
                            f'Error while parsing the incident id with the value: {value}. The given type: '
                            f'{type(value)} is not a valid type for an ID. The supported id types are: int, list and str')
                    elif isinstance(value, str):
                        _ = bytes(value, "utf-8").decode("unicode_escape")
                else:
                    _ = bytes(value, "utf-8").decode("unicode_escape")
            except UnicodeDecodeError as ex:
                error_msg.append(f'Error while parsing the argument: "{_key}" '
                                 f'\nError:\n- "{str(ex)}"')

    if len(error_msg) != 0:
        raise DemistoException('\n'.join(error_msg))

    return True


def apply_filters(incidents: List, args: Dict):
    names_to_filter = set(argToList(args.get('name')))
    types_to_filter = set(argToList(args.get('type')))
    filtered_incidents = []
    for incident in incidents:
        if names_to_filter and incident['name'] not in names_to_filter:
            continue
        if types_to_filter and incident['type'] not in types_to_filter:
            continue

        filtered_incidents.append(incident)

    return filtered_incidents


def add_incidents_link(data: List, platform: str):
    # For XSIAM links
    if platform == 'x2':
        server_url = 'https://' + demisto.getLicenseCustomField('Http_Connector.url')
        for incident in data:
            incident_link = urljoin(server_url,
                                    f'alerts?action:openAlertDetails={incident.get("id")}-investigation')
            incident['alertLink'] = incident_link
    # For XSOAR links
    else:
        server_url = demisto.demistoUrls().get('server')
        for incident in data:
            incident_link = urljoin(server_url, f'#/Details/{incident.get("id")}')
            incident['incidentLink'] = incident_link
    return data


def transform_to_alert_data(incidents: List):
    for incident in incidents:
        incident['hostname'] = incident.get('CustomFields', {}).get('hostname')
        incident['initiatedby'] = incident.get('CustomFields', {}).get('initiatedby')
        incident['targetprocessname'] = incident.get('CustomFields', {}).get('targetprocessname')
        incident['username'] = incident.get('CustomFields', {}).get('username')
        incident['status'] = AlertStatus(incident.get('status')).name
        incident['severity'] = AlertSeverity(incident.get('severity')).name

    return incidents


def search_incidents(args: Dict):   # pragma: no cover
    if not is_valid_args(args):
        return

    if fromdate := arg_to_datetime(args.get('fromdate')):
        from_date = fromdate.isoformat()
        args['fromdate'] = from_date
    if todate := arg_to_datetime(args.get('todate')):
        to_date = todate.isoformat()
        args['todate'] = to_date

    if args.get('trimevents') == '0':
        args.pop('trimevents')

    platform = get_demisto_version().get('platform')

    # handle list of ids
    if args.get('id'):
        args['id'] = ','.join(argToList(args.get('id'), transform=str))

    res: List = execute_command('getIncidents', args, extract_contents=False)
    incident_found: bool = check_if_found_incident(res)
    if incident_found is False:
        if platform == 'x2':
            return 'Alerts not found.', {}, {}
        return 'Incidents not found.', {}, {}

    data = apply_filters(res[0]['Contents']['data'], args)
    data = add_incidents_link(data, platform)
    if not data:
        return 'Incidents not found.', [{}], []

    headers: List[str]
    if platform == 'x2':
        headers = ['id', 'name', 'severity', 'details', 'hostname', 'initiatedby', 'status',
                   'owner', 'targetprocessname', 'username', 'alertLink']
        data = transform_to_alert_data(data)
        md = tableToMarkdown(name="Alerts found", t=data, headers=headers, removeNull=True, url_keys=['alertLink'])
    else:
        headers = ['id', 'name', 'severity', 'status', 'owner', 'created', 'closed', 'incidentLink']
        md = tableToMarkdown(name="Incidents found", t=data, headers=headers)
    return md, data, res


def main():  # pragma: no cover
    args: Dict = demisto.args()
    try:
        readable_output, outputs, raw_response = search_incidents(args)
        if search_results_label := args.get('searchresultslabel'):
            for output in outputs:
                output['searchResultsLabel'] = search_results_label
        results = CommandResults(
            outputs_prefix='foundIncidents',
            outputs_key_field='id',
            readable_output=readable_output,
            outputs=outputs,
            raw_response=raw_response
        )
        return_results(results)
    except DemistoException as error:
        return_error(str(error), error)


if __name__ in ('__main__', '__builtin__', 'builtins'):  # pragma: no cover
    main()

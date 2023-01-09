from datetime import timedelta
import dateparser
import demistomock as demisto
import jwt
import urllib3
from CommonServerPython import *
from IAMApiModule import *


# Disable insecure warnings
urllib3.disable_warnings()

DEFAULT_OUTGOING_MAPPER = "User Profile - SCIM (Outgoing)"
DEFAULT_INCOMING_MAPPER = "User Profile - SCIM (Incoming)"
# The token’s time to live is 1 hour,
# two minutes were subtract for extra safety.
TOKEN_LIFE_TIME = timedelta(minutes=58)
# the lifetime for an JWT token is 90 minutes == 5400 seconds
# 400 seconds were subtract for extra safety.
JWT_LIFETIME = 5000
ERROR_CODES_TO_SKIP = [
    404
]
OAUTH_TOKEN_GENERATOR_URL = 'https://zoom.us/oauth/token'

# ERRORS
INVALID_CREDENTIALS = 'Invalid credentials. Please verify that your credentials are valid.'
INVALID_API_SECRET = 'Invalid API Secret. Please verify that your API Secret is valid.'
INVALID_ID_OR_SECRET = 'Invalid Client ID or Client Secret. Please verify that your ID and Secret is valid.'

'''CLIENT CLASS'''


class Client(BaseClient):
    """ A client class that implements logic to authenticate with Zoom application. """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        account_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        verify=True,
        proxy=False,
    ):
        super().__init__(base_url, verify, proxy)
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        is_jwt = (api_key and api_secret) and not (client_id and client_secret and account_id)
        if is_jwt:
            # the user has chosen to use the JWT authentication method (deprecated)
            self.access_token: str | None = get_jwt_token(api_key, api_secret)  # type: ignore[arg-type]
        else:
            # the user has chosen to use the OAUTH authentication method.
            try:
                self.access_token = self.get_oauth_token()
            except Exception as e:
                demisto.debug(f"Cannot get access token. Error: {e}")
                self.access_token = None

    def generate_oauth_token(self):
        """
    Generate an OAuth Access token using the app credentials (AKA: client id and client secret) and the account id

    :return: valid token
    """
        token_res = self._http_request(method="POST", full_url=OAUTH_TOKEN_GENERATOR_URL,
                                       params={"account_id": self.account_id,
                                               "grant_type": "account_credentials"},
                                       auth=(self.client_id, self.client_secret))
        return token_res.get('access_token')

    def get_oauth_token(self, force_gen_new_token=False):
        """
            Retrieves the token from the server if it's expired and updates the global HEADERS to include it

            :param force_gen_new_token: If set to True will generate a new token regardless of time passed

            :rtype: ``str``
            :return: Token
        """
        now = datetime.now()
        ctx = get_integration_context()

        if not ctx or not ctx.get('token_info').get('generation_time', force_gen_new_token):
            # new token is needed
            oauth_token = self.generate_oauth_token()
            ctx = {}
        else:
            generation_time = dateparser.parse(ctx.get('token_info').get('generation_time'))
            if generation_time:
                time_passed = now - generation_time
            else:
                time_passed = TOKEN_LIFE_TIME
            if time_passed < TOKEN_LIFE_TIME:
                # token hasn't expired
                return ctx.get('token_info').get('oauth_token')
            else:
                # token expired
                oauth_token = self.generate_oauth_token()

        ctx.update({'token_info': {'oauth_token': oauth_token, 'generation_time': now.strftime("%Y-%m-%dT%H:%M:%S")}})
        set_integration_context(ctx)
        return oauth_token

    def error_handled_http_request(self, method, url_suffix='', full_url=None, headers=None,
                                   auth=None, json_data=None, params=None,
                                   return_empty_response: bool = False, resp_type: str = 'json'):

        # all future functions should call this function instead of the original _http_request.
        # This is needed because the OAuth token may not behave consistently,
        # First the func will make an http request with a token,
        # and if it turns out to be invalid, the func will retry again with a new token.
        try:
            return super()._http_request(method=method, url_suffix=url_suffix, full_url=full_url, headers=headers,
                                         auth=auth, json_data=json_data, params=params,
                                         return_empty_response=return_empty_response, resp_type=resp_type)
        except DemistoException as e:
            if ('Invalid access token' in e.message
                    or "Access token is expired." in e.message):
                self.access_token = self.generate_oauth_token()
                headers = {'authorization': f'Bearer {self.access_token}'}
            return super()._http_request(method=method, url_suffix=url_suffix, full_url=full_url, headers=headers,
                                         auth=auth, json_data=json_data, params=params,
                                         return_empty_response=return_empty_response, resp_type=resp_type)

    def test(self):
        """ Tests connectivity with the application. """

        self.get_user('', 'me')
        return 'ok'

    def get_user(self, _, filter_value: str) -> Optional[IAMUserAppData]:
        uri = f'/users/{filter_value}'

        res = self.error_handled_http_request(
            method='GET',
            url_suffix=uri,
            headers={'authorization': f'Bearer {self.access_token}',
                     'Accept': 'application/json',
                     'Content-Type': 'application/json',
                     },
        )
        if res and (not res.get('users')):
            user_app_data = res
            user_id = user_app_data.get('id')
            is_active = True if user_app_data.get('status') == 'active' else False
            email = user_app_data.get('email')
            # the API does not provide user name
            username = ''

            return IAMUserAppData(user_id, username, is_active, user_app_data, email=email)
        return None

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> IAMUserAppData:
        """ Updates a user in the application using REST API.

        :type user_id: ``str``
        :param user_id: ID of the user in the application

        :type user_data: ``Dict[str, Any]``
        :param user_data: User data in the application format

        :return: An IAMUserAppData object that contains the data of the updated user in the application.
        :rtype: ``IAMUserAppData``
        """
        uri = f'/users/{user_id}/status'
        self.error_handled_http_request(
            method='PUT',
            url_suffix=uri,
            json_data=user_data,
            return_empty_response=True,
            headers={'authorization': f'Bearer {self.access_token}',
                     'Accept': 'application/json',
                     'Content-Type': 'application/json',
                     },
        )
        # res is an empty *response object*
        user_app_data: dict = {}
        # if we wanted to disable the user and request succeeded,
        # we get to this line and know the user's status
        is_active = True if user_data.get('action', '') == 'activate' else False
        username = ''

        return IAMUserAppData(user_id, username, is_active, user_app_data)

    def disable_user(self, user_id: str) -> IAMUserAppData:
        """ Disables a user in the application using REST API.

        :type user_id: ``str``
        :param user_id: ID of the user in the application

        :return: An IAMUserAppData object that contains the data of the user in the application.
        :rtype: ``IAMUserAppData``
        """

        user_data = {'action': 'deactivate'}
        return self.update_user(user_id, user_data)

    def enable_user(self, user_id: str) -> IAMUserAppData:
        """ Enables a user in the application using REST API.

        :type user_id: ``str``
        :param user_id: ID of the user in the application

        :return: An IAMUserAppData object that contains the data of the user in the application.
        :rtype: ``IAMUserAppData``
        """

        user_data = {'action': 'activate'}
        return self.update_user(user_id, user_data)

    def get_app_fields(self):
        user_app_data = self.get_user('', 'me')
        if user_app_data:
            return {k: underscoreToCamelCase(k) for k, _ in user_app_data.full_data.items()}
        raise DemistoException('Could not retrieve fields for mapping')

    @staticmethod
    def handle_exception(user_profile: IAMUserProfile,
                         e: Union[DemistoException, Exception],
                         action: IAMActions):
        """ Handles failed responses from the application API by setting the User Profile object with the result.
            The result entity should contain the following data:
            1. action        (``IAMActions``)       The failed action                       Required
            2. success       (``bool``)             The success status                      Optional (by default, True)
            3. skip          (``bool``)             Whether or not the command was skipped  Optional (by default, False)
            3. skip_reason   (``str``)              Skip reason                             Optional (by default, None)
            4. error_code    (``Union[str, int]``)  HTTP error code                         Optional (by default, None)
            5. error_message (``str``)              The error description                   Optional (by default, None)

            Note: This is the place to determine how to handle specific edge cases from the API, e.g.,
            when a DISABLE action was made on a user which is already disabled and therefore we can't
            perform another DISABLE action.

        :type user_profile: ``IAMUserProfile``
        :param user_profile: The user profile object

        :type e: ``Union[DemistoException, Exception]``
        :param e: The exception object - if type is DemistoException, holds the response json object (`res` attribute)

        :type action: ``IAMActions``
        :param action: An enum represents the current action (GET, UPDATE, CREATE, DISABLE or ENABLE)
        """
        if isinstance(e, DemistoException) and e.res is not None:
            error_code = e.res.status_code

            if action == IAMActions.DISABLE_USER and error_code in ERROR_CODES_TO_SKIP:
                skip_message = 'Users is already disabled or does not exist in the system.'
                user_profile.set_result(action=action,
                                        skip=True,
                                        skip_reason=skip_message)

            try:
                resp = e.res.json()
                error_message = get_error_details(resp)
            except ValueError:
                error_message = str(e)
        else:
            error_code = ''
            error_message = str(e)

        user_profile.set_result(action=action,
                                success=False,
                                error_code=error_code,
                                error_message=error_message)

        demisto.error(traceback.format_exc())


'''HELPER FUNCTIONS'''


def get_jwt_token(api_key: str, api_secret: str) -> str:
    """
    Encode the JWT token given the api key and secret
    """
    now = time.time()
    expire_time = int(now) + JWT_LIFETIME
    payload = {
        'iss': api_key,
        'exp': expire_time
    }
    encoded = jwt.encode(payload, api_secret, algorithm='HS256')
    return str(encoded)


def get_error_details(res: Dict[str, Any]) -> str:
    """ Parses the error details retrieved from the application and outputs the resulted string.

    :type res: ``Dict[str, Any]``
    :param res: The error data retrieved from the application.

    :return: The parsed error details.
    :rtype: ``str``
    """
    message = res.get('code', '')
    details = res.get('message', '')
    return f'{message}: {details}'


'''COMMAND FUNCTIONS'''


def test_module(client: Client):
    """Tests connectivity with the client.
    Takes as an argument all client arguments to create a new client
    """
    try:
        client.test()
    except DemistoException as e:
        error_message = e.message
        if 'Invalid access token' in error_message:
            error_message = INVALID_CREDENTIALS
        elif "The Token's Signature resulted invalid" in error_message:
            error_message = INVALID_API_SECRET
        elif 'Invalid client_id or client_secret' in error_message:
            error_message = INVALID_ID_OR_SECRET
        else:
            error_message = f'Problem reaching Zoom API, check your credentials. Error message: {error_message}'
        return error_message
    return 'ok'


def get_mapping_fields(client: Client):
    mapping = client.get_app_fields()
    incident_type_scheme = SchemeTypeMapping(type_name=IAMUserProfile.DEFAULT_INCIDENT_TYPE, fields=mapping)
    return GetMappingFieldsResponse([incident_type_scheme])


def check_authentication_type_arguments(api_key: str, api_secret: str,
                                        account_id: str, client_id: str, client_secret: str):
    if any((api_key, api_secret)) and any((account_id, client_id, client_secret)):
        raise DemistoException("""Too many fields were filled.
                                   You should fill the Account ID, Client ID, and Client Secret fields (OAuth),
                                   OR the API Key and API Secret fields (JWT - Deprecated)""")


def main():  # pragma: no cover
    user_profile = None
    params = demisto.params()
    base_url = params.get('url')
    api_key = params.get('creds_api_key', {}).get('password') or params.get('api_key')
    api_secret = params.get('creds_api_secret', {}).get('password') or params.get('api_secret')
    account_id = params.get('account_id')
    client_id = params.get('credentials', {}).get('identifier')
    client_secret = params.get('credentials', {}).get('password')
    mapper_in = params.get('mapper_in', DEFAULT_INCOMING_MAPPER)
    verify_certificate = not params.get('insecure', False)
    proxy = params.get('proxy', False)
    command = demisto.command()
    args = demisto.args()

    is_disable_enabled = argToBoolean(params.get('disable-user-enabled'))
    is_enable_enabled = argToBoolean(params.get('enable-user-enabled'))

    iam_command = IAMCommand(is_create_enabled=False,
                             is_enable_enabled=is_enable_enabled,
                             is_disable_enabled=is_disable_enabled,
                             is_update_enabled=False,
                             create_if_not_exists=False,
                             mapper_in=mapper_in,
                             # Currently we don't use scim API endpoints, so we don't map the arguments.
                             mapper_out=None,
                             get_user_iam_attrs=['id', 'username', 'email']
                             )
    try:
        check_authentication_type_arguments(api_key, api_secret, account_id, client_id, client_secret)

        client = Client(
            base_url=base_url,
            verify=verify_certificate,
            proxy=proxy,
            api_key=api_key,
            api_secret=api_secret,
            account_id=account_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        if command == 'test-module':
            return_results(test_module(client=client))

        demisto.debug(f'Command being called is {command}')

        '''CRUD commands'''
        if command == 'iam-disable-user':
            user_profile = iam_command.disable_user(client, args)
        if command == 'iam-enable-user':
            user_profile = iam_command.enable_user(client, args)
        if command == 'iam-get-user':
            user_profile = iam_command.get_user(client, args)

        if user_profile:
            return_results(user_profile)

        '''non-CRUD commands'''

        if command == 'get-mapping-fields':
            return_results(get_mapping_fields(client))

    except Exception as e:
        # For any other integration command exception, return an error
        return_error(f'Failed to execute {command} command. Error: {str(e)}')


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()

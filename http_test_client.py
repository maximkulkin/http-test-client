from collections import namedtuple
import json
import logging
import requests
import urllib
import six
import six.moves


class ClientError(Exception):
    def __init__(self, status_code, message):
        if not message:
            message = 'Status code %d' % status_code
        else:
            message += ' (status code %d)' % status_code
        super(ClientError, self).__init__(message)
        self.status_code = status_code


class DummyTransport(object):
    '''
    Transport that just prints executed requests
    '''
    def request(self, url, method=None, headers=None, data=None, **kwargs):
        if data is not None:
            print '%s %s data=%s' % (method, url, json.dumps(data))
        else:
            print '%s %s' % (method, url)

        return Response(200, {}, '')


class HttpTransport(object):
    '''
    HTTP transport. Use base_url to specifying URL prefix (e.g. host/port)
    '''
    def __init__(self, base_url):
        super(HttpTransport, self).__init__()
        self._base_url = base_url
        self._session = requests.Session()

    def request(self, url, method=None, headers=None, data=None, **kwargs):
        request = requests.Request(
            url=self._base_url + url, method=method or 'GET',
            headers=headers or {},
            data=data,
            **kwargs
        )

        return self._session.send(self._session.prepare_request(request))


Response = namedtuple('Response', ['status_code', 'headers', 'text'])


class Client(object):
    '''
    Top level API client object. Holds reference to transport and base url.
    Has cleanup API to allow resources to register cleanup callbacks.
    '''
    logger = logging.getLogger(__module__ + '.Client')

    def __init__(self, transport, url=''):
        """
        Args:
            transport  Instance HttpSession
            url        API URL to access a specific resource
        """
        self._transport = transport
        self._url = url
        self._cleanup = []

        self._client = self

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self._url)

    def add_cleanup(self, url, func):
        '''Add cleanup callback associated with given URL'''
        self._cleanup.append((url, func))

    def remove_cleanup(self, url):
        '''Remove cleanup callbacks associated with given URL'''
        self._cleanup = [(url1, func) for (url1, func) in self._cleanup
                         if url1 != url and not url1.startswith(url + '/')]

    def cleanup(self):
        '''Execute all cleanup callbacks'''
        for _, func in self._cleanup:
            func()
        self._cleanup = []

    def raw_request(self, url, method=None, headers=None, data=None, **kwargs):
        '''
        Send HTTP request through configured transport and return Response object
        '''
        if method is None:
            method = 'GET' if data is None else 'POST'

        url = self._url + url
        if data is not None:
            data = json.dumps(data)

        if headers is None:
            headers = {}

        headers['Content-Type'] = 'application/json'

        self._log_request(url, method=method, headers=headers, data=data)

        response = self._transport.request(
            url=url, method=method, headers=headers, data=data, **kwargs
        )

        self._log_response(response)

        return response

    def request(self, url, method=None, headers=None, data=None, **kwargs):
        '''Send HTTP request and return JSON response data'''
        response = self.raw_request(
            url, method=method, headers=headers, data=data, **kwargs
        )

        if response.status_code not in six.moves.range(200, 299):
            if response.status_code == 404:
                return None
            else:
                raise ClientError(response.status_code, response.text)

        return json.loads(response.text) if len(response.text) > 0 else None

    def _log_request(self, url, method, headers, data):
        """Log request"""
        s = '%s request to %s' % (method, url)
        if headers:
            s += ' headers=%s' % repr(headers)
        if data:
            s += ' body=%s' % data

        self.logger.debug('Sending %s', s)

    def _log_response(self, response):
        """Log response"""
        s = 'code=%d' % response.status_code
        if response.headers:
            s += ' headers=%s' % repr(response.headers)
        if response.text:
            s += ' body=%s' % response.text

        self.logger.debug('Got response %s', s)


class Api(object):
    '''
    Base class for all HTTP APIs. Maintains a client and base url.
    '''
    def __init__(self, client, url, **kwargs):
        """
        Args:
            session  Instance HttpSession
            url      API URL to access a specific resource
            kwargs   Additional properties to store
        """
        self._client = client
        self._url = url
        for k, v in six.iteritems(kwargs):
            setattr(self, k, v)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self._url)


class RestResources(Api):
    '''
    REST resources API implementing access to collection of resources.
    Inner class "Resource" defines API for accessing particular resource.

    Example:

        users = RestResource(client, '/users')
        users.list() # => [{'id': '1', 'name': 'John'}, ... ]
        users.create(name='Jane') # => {'id': '2'}

        users['2'].get() # => {'id': '2', 'name': 'Jane'}
        users['2'].update(name='Jane Doe')
        users['2'].delete()

    Uses Client's Cleanup API to register created resources for cleanup.
    '''
    def list(self):
        return self._client.request(self._url)

    def create(self, **kwargs):
        result = self._client.request(self._url, method='POST', data=kwargs)
        if isinstance(result, dict) and 'id' in result:
            id = result['id']
            self._client.add_cleanup(
                self._url + '/' + urllib.quote(id), self[id].delete,
            )
        return result

    def __getitem__(self, id):
        return self.Resource(
            self._client, self._url + '/' + urllib.quote(id),
            parent_ids=getattr(self, 'parent_ids', []) + [id],
        )

    class Resource(Api):
        def get(self):
            return self._client.request(self._url)

        def update(self, **kwargs):
            return self._client.request(self._url, method='PUT', data=kwargs)

        def delete(self):
            response = self._client.raw_request(self._url, method='DELETE')

            if response.status_code not in six.moves.range(200, 299) and \
                    response.status_code != 404:
                raise ClientError(response.status_code, response.text)

            self._client.remove_cleanup(self._url)


def api(path, klass):
    '''
    Returns property that instantiates and returns specified Api class instance
    passing it client and suburl, derived from self url and given path.

    :param path: (string) URI path relative to parent resource
    :param klass: (Api) Api class to instantiate
    :return: Property descriptor
    '''
    assert issubclass(klass, Api), 'Resource klass should be subclass of Api'

    def get(self):
        return klass(self._client, self._url + path)

    return property(get)


def resources(path, klass=RestResources):
    return api(path, klass)

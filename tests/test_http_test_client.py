from http_test_client import Response, RestResources, ClientError, \
    HttpTransport, Client, resources
from mockito import when, verify, verifyNoMoreInteractions
import mockito as m
import pytest
import responses as responses_
import json


class TestHttpTransport:
    @pytest.fixture
    def transport(self):
        return HttpTransport('http://localhost:8888/api')

    @pytest.fixture
    def responses(self):
        with responses_.RequestsMock() as responses:
            yield responses

    def test_sending_requests(self, transport, responses):
        responses.add(responses.GET, 'http://localhost:8888/api/foo',
                      body='["foo", "bar"]', status=200)

        response = transport.request('/foo')

        assert response is not None
        assert response.status_code == 200
        assert response.text == '["foo", "bar"]'


class TestTransport(object):
    def request(self, url, method=None, headers=None, data=None, **kwargs):
        return Response(200, {}, '')

    def __repr__(self):
        return '<TestTransport>'


def verify_request(transport, url=m.any(), method=m.any(),
                   headers=m.any(), data=m.any()):
    verify(transport).request(url=url, method=method, headers=headers, data=data)


class ClenaupCallbacks:
    def __init__(self):
        self.calls = []

    def cleanup1(self):
        self.calls.append('cleanup1')

    def cleanup2(self):
        self.calls.append('cleanup2')


class TestClient:
    @pytest.fixture
    def transport(self):
        return m.spy(TestTransport())

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_url(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo/bar/baz')

        verify_request(transport, url='/foo/bar/baz')

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_base_url(self, transport, request_method):
        client = Client(transport, '/api')

        request_method(client, '/foo/bar/baz')

        verify_request(transport, url='/api/foo/bar/baz')

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_method_defaults_to_get(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo')

        verify_request(transport, method='GET')

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_method_defaults_to_post_if_data(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo', data=[1, 2, 3])

        verify_request(transport, method='POST')

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_custom_method(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo', method='PUT')

        verify_request(transport, method='PUT')

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_default_headers(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo')

        verify_request(transport, headers={'Content-Type': 'application/json'})

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_custom_headers(self, transport, request_method):
        client = Client(transport)

        request_method(client, '/foo', headers={'AuthToken': '123'})

        verify_request(transport, headers={'AuthToken': '123',
                                           'Content-Type': 'application/json'})

    @pytest.mark.parametrize('request_method', [Client.raw_request, Client.request])
    def test_request_data_automatically_json_serialized(self, transport, request_method):
        client = Client(transport)

        data = {'foo': 'hello', 'bar': 123}
        request_method(client, '/foo', data=data)

        verify_request(transport, data=json.dumps(data))

    def test_raw_request_returns_response_object(self, transport):
        response = Response(201, {}, 'hello, world!')
        when(transport).request(url='/foo', method='GET',
                                headers=m.any(), data=m.any()).thenReturn(response)

        client = Client(transport)
        assert client.raw_request('/foo') == response

    def test_request_returns_parsed_json(self, transport):
        data = {'foo': 'hello', 'bar': 123}

        when(transport).request(
            url='/foo', method='GET',
            headers=m.any(), data=m.any(),
        ).thenReturn(Response(200, {}, json.dumps(data)))

        client = Client(transport)
        assert client.request('/foo') == data

    def test_request_returns_None_if_body_is_empty(self, transport):
        data = {'foo': 'hello', 'bar': 123}

        when(transport).request(
            url='/foo', method='GET',
            headers=m.any(), data=m.any(),
        ).thenReturn(Response(200, {}, ''))

        client = Client(transport)
        assert client.request('/foo') is None

    def test_request_returns_None_if_response_status_code_is_404(self, transport):
        when(transport).request(
            url=m.any(), method=m.any(),
            headers=m.any(), data=m.any(),
        ).thenReturn(Response(404, {}, ''))

        client = Client(transport)
        assert client.request('/foo') is None

    def test_request_raises_ClientError_if_response_status_code_is_not_2xx(self, transport):
        when(transport).request(
            url=m.any(), method=m.any(),
            headers=m.any(), data=m.any(),
        ).thenReturn(Response(400, {}, ''))

        client = Client(transport)

        with pytest.raises(ClientError) as exc:
            client.request('/foo')
        assert exc.value.status_code == 400

    def test_cleanup_executes_all_registered_cleanup_callbacks(self, transport):
        class Callbacks:
            def __init__(self):
                self.calls = []

            def cleanup1(self):
                self.calls.append('cleanup1')

            def cleanup2(self):
                self.calls.append('cleanup2')

        callbacks = Callbacks()

        client = Client(transport)
        client.add_cleanup('/foo', callbacks.cleanup1)
        client.add_cleanup('/bar', callbacks.cleanup2)

        client.cleanup()

        assert sorted(callbacks.calls) == sorted(['cleanup1', 'cleanup2'])

    def test_removing_cleanup_callback(self, transport):
        class Callbacks:
            def __init__(self):
                self.calls = []

            def cleanup1(self):
                self.calls.append('cleanup1')

            def cleanup2(self):
                self.calls.append('cleanup2')

        callbacks = Callbacks()

        client = Client(transport)
        client.add_cleanup('/foo', callbacks.cleanup1)
        client.add_cleanup('/bar', callbacks.cleanup2)
        client.remove_cleanup('/foo')

        client.cleanup()

        assert sorted(callbacks.calls) == sorted(['cleanup2'])

    def test_multiple_cleanups_for_same_url(self, transport):
        callbacks = ClenaupCallbacks()

        client = Client(transport)
        client.add_cleanup('/foo', callbacks.cleanup1)
        client.add_cleanup('/foo', callbacks.cleanup2)

        client.cleanup()

        assert sorted(callbacks.calls) == sorted(['cleanup1', 'cleanup2'])

    def test_removal_of_multiple_cleanups_for_same_url(self, transport):
        callbacks = ClenaupCallbacks()

        client = Client(transport)
        client.add_cleanup('/foo', callbacks.cleanup1)
        client.add_cleanup('/foo', callbacks.cleanup2)
        client.remove_cleanup('/foo')

        client.cleanup()

        assert callbacks.calls == []


class TestRestResources:
    @pytest.fixture
    def session(self):
        session = m.mock()
        return session

    def test_resources_list(self, session):
        when(session).request('/users').thenReturn(["foo", "bar"])

        assert RestResources(session, '/users').list() == ['foo', 'bar']

    def test_passing_extra_params_to_resources_list(self, session):
        when(session).request('/users', params={'baz': 'bam'})\
            .thenReturn(["foo", "bar"])

        assert RestResources(session, '/users').list(params={'baz': 'bam'}) == ['foo', 'bar']

    def test_resources_create(self, session):
        when(session)\
            .request('/users', method='POST', data={'foo': 'bar', 'baz': 123})\
            .thenReturn({'id': 'id1'})

        assert RestResources(session, '/users')\
            .create({'foo': 'bar', 'baz': 123}) == {'id': 'id1'}

    def test_passing_extra_params_to_resources_create(self, session):
        when(session)\
            .request('/users', method='POST', data={'foo': 'bar', 'baz': 123},
                     params={'bam': '123'})\
            .thenReturn({'id': 'id1'})

        assert RestResources(session, '/users')\
            .create({'foo': 'bar', 'baz': 123}, params={'bam': '123'}) == {'id': 'id1'}

    def test_resource_get(self, session):
        when(session).request('/users/user1')\
            .thenReturn({'id': 'user1', 'name': 'John'})

        assert RestResources(session, '/users')['user1']\
            .get() == {'id': 'user1', 'name': 'John'}

    def test_passing_extra_params_to_resource_get(self, session):
        when(session).request('/users/user1', params={'foo': 'bar'})\
            .thenReturn({'id': 'user1', 'name': 'John'})

        assert RestResources(session, '/users')['user1']\
            .get(params={'foo': 'bar'}) == {'id': 'user1', 'name': 'John'}

    def test_resource_update(self, session):
        when(session).request('/users/user1', method='PUT', data={'name': 'Jane'})\
            .thenReturn({'id': 'user1', 'name': 'Jane'})

        assert RestResources(session, '/users')['user1']\
            .update({'name': 'Jane'}) == {'id': 'user1', 'name': 'Jane'}

    def test_passing_extra_params_to_resource_update(self, session):
        when(session).request('/users/user1', method='PUT',
                              data={'name': 'Jane'}, params={'foo': 'bar'})\
            .thenReturn({'id': 'user1', 'name': 'Jane'})

        assert RestResources(session, '/users')['user1']\
            .update({'name': 'Jane'}, params={'foo': 'bar'}) == {'id': 'user1', 'name': 'Jane'}

    def test_resource_delete(self, session):
        when(session).raw_request(m.any(), method='DELETE')\
            .thenReturn(Response(204, {}, ''))

        RestResources(session, '/users')['user1'].delete()

        verify(session).raw_request('/users/user1', method='DELETE')

    def test_passing_extra_params_to_resource_delete(self, session):
        when(session).raw_request(m.any(), method='DELETE', params={'foo': 'bar'})\
            .thenReturn(Response(204, {}, ''))

        RestResources(session, '/users')['user1'].delete(params={'foo': 'bar'})

        verify(session).raw_request('/users/user1', method='DELETE',
                                    params={'foo': 'bar'})

    def test_resource_delete_ignores_404_response(self, session):
        when(session).raw_request('/users/user1', method='DELETE')\
            .thenReturn(Response(404, {}, 'user not found'))

        RestResources(session, '/users')['user1'].delete()

        verify(session).raw_request('/users/user1', method='DELETE')

    def test_resource_delete_raises_ClientError_if_status_code_is_wrong(self, session):
        when(session).raw_request('/users/user1', method='DELETE')\
            .thenReturn(Response(500, {}, 'internal server error'))

        with pytest.raises(ClientError):
            RestResources(session, '/users')['user1'].delete()

    def test_registering_cleanup_on_create(self, session):
        when(session).request('/users', method='POST', data=m.any())\
            .thenReturn({'id': 'john'})

        RestResources(session, '/users').create({'name': 'John Doe'})

        func_captor = m.captor(m.arg_that(callable))

        verify(session).add_cleanup('/users/john', func_captor)


        when(session).raw_request(m.any(), method='DELETE')\
            .thenReturn(Response(204, {}, ''))

        (func_captor.value)()

        verify(session).raw_request('/users/john', method='DELETE')

    def test_unregistering_cleanup_on_delete(self, session):
        RestResources(session, '/users')['john'].delete()

        verify(session).remove_cleanup('/users/john')

    def test_custom_collection_methods(self, session):
        class UserResources(RestResources):
            def search(self, name=None):
                return self._client.request(self._url + '/search', method='POST',
                                            data={'name': name})

        users = UserResources(session, '/users')

        found_users = [{'id': 'user5', 'name': 'foo'},
                       {'id': 'user25', 'name': 'foobar'}]
        when(session).request('/users/search', method='POST', data={'name': 'foo'})\
            .thenReturn(found_users)

        assert users.search('foo') == found_users

    def test_custom_resource_methods(self, session):
        class UserResources(RestResources):
            class Resource(RestResources.Resource):
                def tap(self):
                    return self._client.request(self._url + '/tap', method='POST')

        users = UserResources(session, '/users')

        users['user3'].tap()

        verify(session).request('/users/user3/tap', method='POST')

    def test_nesting_resources(self, session):
        class UserResources(RestResources):
            class Resource(RestResources.Resource):
                articles = resources('/articles')

        users = UserResources(session, '/users')

        articles = [{'id': 'article1', 'title': 'Article 1'},
                    {'id': 'article2', 'title': 'Article 2'}]

        when(session).request('/users/user1/articles').thenReturn(articles)

        assert users['user1'].articles.list() == articles

        when(session).request('/users/user1/articles/%s' % articles[0]['id'])\
            .thenReturn(articles[0])

        assert users['user1'].articles[articles[0]['id']].get() == articles[0]

    def test_nested_resources_registering_cleanup_on_create(self, session):
        class UserResources(RestResources):
            class Resource(RestResources.Resource):
                articles = resources('/articles')

        users = UserResources(session, '/users')

        when(session).request('/users/user1/articles', method='POST', data=m.any())\
            .thenReturn({'id': 'article1'})

        users['user1'].articles.create({'name': 'John Doe'})

        func_captor = m.captor(m.arg_that(callable))

        verify(session).add_cleanup('/users/user1/articles/article1', func_captor)


        when(session).raw_request(m.any(), method='DELETE')\
            .thenReturn(Response(204, {}, ''))

        (func_captor.value)()

        verify(session).raw_request('/users/user1/articles/article1', method='DELETE')

    def test_unregistering_cleanup_on_delete(self, session):
        class UserResources(RestResources):
            class Resource(RestResources.Resource):
                articles = resources('/articles')

        users = UserResources(session, '/users')

        when(session).raw_request(m.any(), method='DELETE')\
            .thenReturn(Response(204, {}, ''))

        users['john'].articles['article1'].delete()

        verify(session).remove_cleanup('/users/john/articles/article1')

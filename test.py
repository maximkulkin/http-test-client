from http_test_client import Client, DummyTransport, RestResources, resources

class ArticleResources(RestResources):
    def search(self, query):
        return self._client.request(self._url + '/search', data={'query': query})

    class Resource(RestResources.Resource):
        def publish(self):
            return self._client.request(self._url + '/publish', method='POST')

        comments = resources('/comments')

class MyClient(Client):
    users = resources('/users')
    articles = resources('/articles', ArticleResources)

client = MyClient(DummyTransport())

# managing resources
client.users.list() # => [{'id': '1', 'name': 'John'}, ...]
client.users.create(name='Jane') # => {'id': '2'}
client.users['1'].get() # => {'id': '1', 'name': 'John'}
client.users['1'].delete()

# delete all resources that were created during this client session
client.cleanup()

# custom action
client.articles['123'].publish()

# nested resources
client.articles['123'].comments.list()

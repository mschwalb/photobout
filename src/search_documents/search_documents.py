from google.appengine.api import search

class SearchDocument(object):
    def __init__(self, index_name):
        self.index = search.Index(name=index_name)

    def make_document(self, id, fields):
        document = search.Document(doc_id=str(id), fields=fields)
        self.index.put(document)

    def make_fields(self, kwargs, build_suggestions):
        fields = []
        for name, value in kwargs.iteritems():
            if name in self.fields:
                fields.append(self.fields[name](name=name, value=value))
        if build_suggestions:
            if kwargs.get('name'):
                fields.append(search.TextField(name='suggestions', value=self.build_suggestions(kwargs.get('name'))))
        return fields

    def create(self, id, build_suggestions=True, **kwargs):
        self.make_document(id, self.make_fields(kwargs, build_suggestions))

    def build_suggestions(self, *strings):
        a=set()
        for string in strings:
            if not string:
                continue
            j=1
            while True:
                for i in range(len(string)-j+1):
                    a.add(string[i:i+j])
                if j==len(string):
                    break
                j+=1
        return ' '.join(a)

    def fetch_with_cursor(self, query, cursor, **query_options):
        result = self.index.search(query=search.Query(query_string=query,
                                                      options=search.QueryOptions(cursor=cursor,**query_options)))
        response = {}
        response['results'] = prepare_search_response(result.results)
        response['cursor'] = result.cursor.web_safe_string if result.cursor else None
        return response

    def fetch_with_web_safe_string(self, query, web_safe_string, **query_options):
        cursor = search.Cursor(web_safe_string=web_safe_string) if web_safe_string else search.Cursor()
        return self.fetch_with_cursor(query,
                                      cursor,
                                      **query_options)

    def fetch(self, string):
        results = self.index.search(string).results
        return prepare_search_response(results)


def prepare_search_response(results):
    response = []
    for result in results:
        result_dict = {}
        result_dict['id'] = result.doc_id
        result_dict['fields'] = {}
        for field in result.fields:
            result_dict['fields'][field.name] = field.value
        response.append(result_dict)
    return response


class BoutDocument(SearchDocument):
    def __init__(self):
        self.index_name = 'bouts'
        self.fields = {'name': search.TextField, 'description': search.TextField}
        super(BoutDocument, self).__init__(self.index_name)

class UserDocument(SearchDocument):
    def __init__(self):
        self.index_name = 'users'
        self.fields = {'name': search.TextField, 'facebook_id': search.TextField}
        super(UserDocument, self).__init__(self.index_name)



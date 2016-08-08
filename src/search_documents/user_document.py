import logging

from google.appengine.api import search
from model.user import User
from model.third_party_user import ThirdPartyUser


INDEX = 'user_search_index'
LIST_DELIMITER =  " , "
FIELDS = (NAME, SUGGESTIONS, FACEBOOK_ID) =['name', 'suggestions', 'facebook_id']
INDICES =  {NAME: 0, SUGGESTIONS: 1, FACEBOOK_ID: 2}


def index():
    return search.Index(name=INDEX)

def build_suggestions(*strings):
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

def get_by_user(user):
    return get_by_id(user.email)

def get_by_id(id):
    doc = index().get(str(id))
    return UserDocument(doc) if doc else None

def update(user):
    #either replace the entire list or add a new entry to the list
    doc = get_by_user(user)
    if not doc:
        logging.warning("Document for user %s not found. Did not update" %  user.email)
        return

    create_user_search_document(user)

def update_attrs(doc_id, **kwargs):
    #either replace the entire list or add a new entry to the list
    document = get_by_id(doc_id)
    build_suggestions = NAME in kwargs
    new_fields = {}

    new_fields[NAME] = kwargs.get(NAME, document.name)

    if not build_suggestions:
        new_fields[SUGGESTIONS] = document.suggestions
    else:
        new_fields['other_names'] =  _get_third_party_names(User.get_by_email(doc_id))
    _create(doc_id,**new_fields)

def _get_third_party_names(user):
    other_names = []
    for third_party_user in ThirdPartyUser.for_user(user):
        if third_party_user.id != user.name:
            other_names.append(third_party_user.id)
    return other_names

def create_user_search_document(user, save = True):
    other_names = _get_third_party_names(user)
    facebook_user = ThirdPartyUser.for_(user, 'FB')
    facebook_id = facebook_user.network_id if facebook_user else None
    return _create(user.email, user.name, facebook_id, other_names, should_save = save)

def _create(doc_id, name = None, facebook_id = None, other_names = None, suggestions = None, should_save = True):
    suggestions = suggestions or build_suggestions(name,*(other_names or []))
    fields = [search.TextField(name=NAME, value=name), search.TextField(name=FACEBOOK_ID, value=facebook_id), search.TextField(name=SUGGESTIONS, value=suggestions)]

    document = search.Document(
        doc_id = str(doc_id),
        fields = fields
    )
    should_save and put(document)
    return document

def put(documents):
    index().put(documents)

def as_list(value):
    return value.split(LIST_DELIMITER)

def fetch_with_web_safe_string(query, web_safe_string, **query_options):
    return fetch(query,
                 search.Cursor(web_safe_string = web_safe_string),
                 **query_options)

def fetch(query, cursor, **query_options):
    index = search.Index(INDEX)
    return UserSearchResults(index.search(query = search.Query(
    query_string = query,
        options = search.QueryOptions(
            cursor = cursor,
            **query_options ))), query_options.get('returned_fields', None))

def fetch_all(query, mapper=None, **query_options):
    batch_size = 1000
    query_options["limit"] = batch_size
    offset = 0
    cursor =  search.Cursor()
    search_results = fetch(query, cursor, **query_options)
    count = search_results.number_found
    while offset < count:
        for result in search_results:
            yield mapper(result) if mapper else result
        offset += batch_size
        cursor = search_results.cursor
        search_results = fetch(query, cursor, **query_options)

class UserSearchResults(object):
    def __init__(self, search_results, returned_fields = None):
        self._search_results = search_results
        if returned_fields:
            sorted_fields = sorted(returned_fields,
                                   lambda field1, field2: INDICES[field1] - INDICES[field2])
            self._indices_map = dict(zip(sorted_fields, range(len(sorted_fields))))
        else:
            self._indices_map = INDICES

    def __iter__(self):
        for result in self._search_results:
            yield UserDocument(result, self._indices_map)

    @property
    def cursor(self):
        return self._search_results.cursor

    @property
    def number_found(self):
        return self._search_results.number_found

    @property
    def results(self):
        return [UserDocument(result, self._indices_map) for result in self._search_results.results]

class UserDocument(object):
    def __init__(self, doc, indices=INDICES):
        self._doc = doc
        self._indices_map = indices

    def _value(self, name, mapper=None):
        value = None
        try:
            value =  self._doc.fields[self._indices_map[name]].value
        except IndexError:
            value = None
        return mapper(value) if mapper else value

    @property
    def doc_id(self):
        return self._doc.doc_id

    @property
    def name(self):
        return self._value(NAME)

    @property
    def facebook_id(self):
        return self._value(FACEBOOK_ID)

    @property
    def suggestions(self):
        return self._value(SUGGESTIONS)
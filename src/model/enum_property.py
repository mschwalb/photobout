from google.appengine.ext import db

class EnumProperty(db.IntegerProperty):
    def __init__(self, cls, **attrs):
        super(EnumProperty, self).__init__(**attrs)
        self.__cls__ = cls

    def validate(self,  value):
        return value
        
    def get_value_for_datastore(self,  model_instance):
        result =  super(EnumProperty,  self).get_value_for_datastore(model_instance)
        return  int(result)

    def make_value_from_datastore(self,  value):
        return super(EnumProperty, self).make_value_from_datastore(self.__cls__(value))


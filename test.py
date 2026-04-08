from src import libimportx

import json
examplekey="value"
examplelist=[1,2,3]
exampledict={"key":"value","key2":[1,2,3]}

assert libimportx.resolveIdentifier("examplekey")==examplekey
assert libimportx.resolveIdentifier("examplelist[1]")==examplelist[1]
assert libimportx.resolveIdentifier("exampledict['key']")==exampledict['key']
assert libimportx.resolveIdentifier('exampledict["key2"][2]')==exampledict["key2"][2]
assert libimportx.resolveIdentifier("exampledict")==exampledict
assert libimportx.resolveIdentifier("exampledict['key2']")==exampledict['key2']
assert libimportx.resolveIdentifier("exampledict.key2")==exampledict['key2']

assert libimportx.resolveIdentifier("json.dumps")==json.dumps
assert libimportx.resolveIdentifier("json['dumps']")==json.dumps
assert libimportx.resolveIdentifier("json.dumps.__name__")=="dumps"
assert libimportx.resolveIdentifier("['json'].dumps")==json.dumps
assert libimportx.resolveIdentifier("['json']['dumps']")==json.dumps
assert libimportx.resolveIdentifier("['json'].dumps.__name__")=="dumps"

print("All tests passed")

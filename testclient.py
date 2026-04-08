from src import libimportx
import json
variable="value"
mydict={"key":"value","key2":[1,2,3]}
mylist=[1,2,3]
myflag=False
myfile=open("testclient.py","r")
def myfunction():
    global myflag
    myflag=not myflag
    return myflag

libimportx.exportx()
print("The file is not importx'ed")


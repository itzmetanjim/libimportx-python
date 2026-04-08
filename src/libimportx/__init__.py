
import re
import socket
import json
import os
import sys

__version__="1.0.0"
handle_counter=0
handleMap=dict()
rHandleMap=dict()

# def parseIdentifier(a):
#     raw_parts=re.split(r'\.(?=(?:[^"]*"[^"]*")*[^"]*$)|(?=\[)|(?<=\])',a    )
#     parts=[]
#     for i in raw_parts:
#         if i!="":parts.append(i)
#     return parts
def parseIdentifier(a):
    pattern = r'\[(?:".*?"|\'.*?\'|[^\]])*?\]|[^.\[\]]+'
    parts=re.findall(pattern,a)
    return [p.strip(".") for p in parts if p]
def resolveIdentifier(a,nsp=None,parent=False):
    if nsp==None:
        nsp = sys.modules['__main__']
    parsed=parseIdentifier(a)
    current=nsp
    if(parent):
        child=parsed[-1]
        parsed=parsed[:-1]
        #no special case if its empty; the for loop will just not run
    global handleMap
    for i in parsed:
        if (i.startswith("['") or i.startswith('["')):
            if (not (i.endswith("']") or i.endswith('"]'))):
                raise SyntaxError(f"Unmatched bracket or quote in {a}: {i}")
            ssub="\""+i[2:-2]+"\""
            sub=json.loads(ssub)
            if (sub.startswith(("function ","opaque "))):
                if sub in handleMap:
                    current=handleMap[sub]
                else:
                    raise NameError(f"Handle {sub} not found in {a}")
            elif (hasattr(current, "__getitem__")):
                current=current[sub]
            else:
                current=getattr(current,sub)
        elif (i.startswith("[")):
            if (not i.endswith("]")):
                raise SyntaxError(f"Unmatched bracket in {a}: {i}")
            index=int(i[1:-1])
            current=current[index]
        else:
            if (i.startswith(("function ","opaque "))):
                if i in handleMap:
                    current=handleMap[i]
                else:
                    raise NameError(f"Handle {i} not found in {a}")
            elif (hasattr(current, "__getitem__")):
                current=current[i]
            else:
                current=getattr(current,i)
    if(parent):
        return current,child
    #else:
    return current
def recvLine(s,l):
    buffer=l
    while b"\n" not in buffer:
        chunk=s.recv(1024)
        if not chunk:
            break
        buffer+=chunk
    line,sep,leftover=buffer.partition(b"\n")
    return line+sep,leftover
def tname(x):
    R=x.__class__
    if(R.__module__!="builtins"):
        return R.__module__+"."+R.__qualname__
    else:
        return R.__qualname__
def monoencode(t):
    if (callable(t)):typ="function"
    else:typ="opaque"
    global handle_counter
    global handleMap
    global rHandleMap
    if(id(t) in rHandleMap):
        handle=rHandleMap[id(t)]
    else:
        handle=typ+" "+hex(handle_counter)[2:]
        handle_counter+=1
        handleMap[handle]=t
        rHandleMap[id(t)]=handle
    if(typ=="function"):
        return {"__libimportx_foreign_type__": "function", "handle": handle}
    else:
        return {"__libimportx_foreign_type__": "opaque",
                "type": tname(t), "handle": handle}

def convert(x):
    return json.dumps(x,default=monoencode)
def deconvert(x):
    if isinstance(x,dict):
        if "__libimportx_foreign_type__" in x:
            handle=x.get("handle","")
            if handle in handleMap:
                return handleMap[handle]
            #else:
            return x
        #else:
        return {k:deconvert(v) for k,v in x.items()}
    elif isinstance(x,list):
        return [deconvert(i) for i in x]
    #else:
    return x
def setIdentifier(ide,v,nsp=None):
    if nsp==None:nsp=sys.modules["__main__"]
    p,last=resolveIdentifier(ide,nsp=nsp,parent=True)
    if (last.startswith("['") or last.startswith('["')):
        if(not(last.endswith("']") or last.endswith('"]'))):
            raise SyntaxError(f"Unmatched bracket or quote in {ide}: {last}")
        ssub='"'+last[2:-2]+'"'
        sub=json.loads(ssub)
        if hasattr(p,"__setitem__"):
            p[sub]=v
        else:
            setattr(p,sub,v)
    elif (last.startswith("[")):
        if(not last.endswith("]")):
            raise SyntaxError(f"Unmatched bracket in {ide}: {last}")
        idx=int(last[1:-1])
        p[idx]=v
    else:
        if hasattr(p,"__setitem__"):
            p[last]=v
        else:
            setattr(p,last,v)
def exportx(root=None):
    global handle_counter
    global handleMap
    if os.environ.get("LIBIMPORTX")!="true":
        return False

    lihost=os.environ.get("LIBIMPORTX_HOST")
    litoken=os.environ.get("LIBIMPORTX_TOKEN")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        try:
            s.connect(lihost)
            s.sendall(litoken.encode()+b"\n")
            data=s.recv(2).decode()
            if data!="+\n":
                raise RuntimeError("Invalid token (this should never happen)")
            leftover=b""
            while True:
                line,leftover=recvLine(s,leftover)
                if not line:
                    exit(0)
                line=line.decode().rstrip("\n")
                data=json.loads(line)
                dtype=data.get("type","")
                if dtype=="":
                    s.sendall(b'-{"type":"InvalidRequest","message":"Missing '
                                  b'field `type`"}\n')
                elif dtype=="read":
                    identifier=data.get("identifier","")
                    if identifier=="":
                        s.sendall(b'-{"type":"InvalidRequest","message":"Missin'
                                      b'g field `identifier`"}\n')
                    else:
                        try:
                            uvalue=resolveIdentifier(identifier,nsp=root)
                            value=convert(uvalue)
                            s.sendall(b"+"+value.encode()+b"\n")
                        except Exception as e:
                            error={"type":tname(e),"message":str(e)}
                            s.sendall(b"-"+json.dumps(error).encode()+b"\n")
                elif dtype=="call":
                    identifier=data.get("identifier","")
                    args=data.get("args",[])
                    kwargs=data.get("kwargs",{})
                    if identifier=="":
                        s.sendall(b'-{"type":"InvalidRequest","message":"Missin'
                                      b'g  field `identifier`"}\n')
                    else:
                        try:
                            func=resolveIdentifier(identifier,nsp=root)
                            uvalue=func(*deconvert(args),**deconvert(kwargs))
                            value=convert(uvalue)
                            s.sendall(b"+"+value.encode()+b"\n")
                        except Exception as e:
                            error={"type":tname(e),"message":str(e)}
                            s.sendall(b"-"+json.dumps(error).encode()+b"\n")
                elif dtype=="set":
                    identifier=data.get("identifier","")
                    value=data.get("value",None)
                    if identifier=="":
                        s.sendall(b'-{"type":"InvalidRequest","message":"Missin'
                                      b'g field `identifier`"}\n')
                    else:
                        try:
                            setIdentifier(identifier,deconvert(value),nsp=root)
                            s.sendall(b"+\n")
                        except Exception as e:
                            error={"type":tname(e),"message":str(e)}
                            s.sendall(b"-"+json.dumps(error).encode()+b"\n")
        except Exception as e:
            print(f"Failed to connect to {lihost}: {e}")
            exit(1)

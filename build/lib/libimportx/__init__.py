#SPDX: GPL-3.0-or-later
EXTENSION_TABLE={
    ".py":"python3 $IN",
    ".js":"node $IN",
    ".rb":"ruby $IN",
    ".lua":"lua $IN",
    ".java":"java $IN",
    ".c":"gcc $IN -o $OUT",
    ".cpp":"g++ $IN -o $OUT",
    ".rs":"rustc $IN -o $OUT",
    ".go":"go run $IN",
    ".sh":"bash $IN",
    ".ps1":"pwsh -File $IN",
    ".php":"php $IN",
    ".pl":"perl $IN",
    ".r":"Rscript $IN"
}
import shutil
import re
import socket
import json
import os
import sys
import tempfile
import uuid
import subprocess
import shlex
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

def monoencode_host(t):
    if (hasattr(t,"_handle") and t._handle!=None):
        return {"__libimportx_foreign_type__":"function" if\
                getattr(t,"_type",None) is None else "opaque",\
                "handle":t._handle,
                "type":getattr(t,"_type","")}
    return monoencode(t)

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
            data, leftover=recvLine(s,b"")
            if data!=b"+\n":
                raise RuntimeError("Invalid token (this should never happen)")
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
                            s.sendall(b'+"OK"\n')
                        except Exception as e:
                            error={"type":tname(e),"message":str(e)}
                            s.sendall(b"-"+json.dumps(error).encode()+b"\n")
        except Exception as e:
            print(f"Failed to connect to {lihost}: {e}")
            exit(1)

class ImportxBase():
    def __init__(self,sock,handle=None):
            self._sock=sock
            self._handle=handle #none for module
            self._leftover=b""
    def _make_req(self,dtype,ide,**kwargs):
        fide=ide
        if self._handle:
            if hasattr(ide,"_handle"):
                inner=ide._handle
            else:
                inner=ide

            if ide != None:
                fide=self._handle+\
                    "["+json.dumps(inner,default=monoencode_host)+"]"
            else:
                fide=self._handle
        req={"type":dtype,"identifier":fide,**kwargs}
        self._sock.sendall((json.dumps(req,default=monoencode_host)+"\n")\
                           .encode())
        line,lo=recvLine(self._sock,self._leftover)
        self._leftover=lo
        if not line:
            raise EOFError("Client closed connection")
        prefix=line[:1]
        content=line[1:].decode()
        if prefix==b"-":
            error=json.loads(content)
            etype=error.get("type","Exception")
            emesg=error.get("message","")
            raise Exception(f"{etype}: {emesg}")
        return self._deconvert_host(json.loads(content))
    def _deconvert_host(self,x):
        if isinstance(x,dict):
            if "__libimportx_foreign_type__" in x:
                handle=x.get("handle","")
                typ=x.get("type",None)
                return ImportxOpaque(handle,typ,self._sock)
            #else:
            return ImportxNamespace({k:self._deconvert_host(v)\
                                     for k,v in x.items()})
        elif isinstance(x,list):
            return [self._deconvert_host(i) for i in x]
        #else:
        return ImportxNamespace(x) if isinstance(x,dict) else x
    def __getattr__(self, attr):
        return self._make_req("read",attr)
    def __setattr__(self,attr,value):
        if attr.startswith("_"):
            super().__setattr__(attr,value)
        else:
            self._make_req("set",attr,value=value)
    def __getitem__(self,item):
        return self._make_req("read",item)
    def __setitem__(self,item,value):
        self._make_req("set",item,value=value)

class ImportxOpaque(ImportxBase):
    def __init__(self,handle,typ,sock):
        super().__init__(sock,handle=handle)
        self._type=typ
    def __call__(self,*args,**kwargs):
        return self._make_req("call",None,args=args,\
                              kwargs=kwargs)

class ImportxModule(ImportxBase):
    def __init__(self,sock,process,tempdir=None):
        super().__init__(sock)
        self._process=process
        self._tempdir=tempdir
    def __del__(self):
        try:
            self._sock.close()
            self._process.terminate()
            shutil.rmtree(self._tempdir)
        except:
            pass

class ImportxNamespace(dict):
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(f"{attr}")
    def __setattr__(self,attr,value):
        self[attr]=value

def importx(filepath,cmd=None):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File {filepath} does not exist")
    tempdir=tempfile.mkdtemp(prefix="libx_")
    sockpath=os.path.join(tempdir,"libx.sock")
    token=str(uuid.uuid4())
    if not cmd:
        ext=os.path.splitext(filepath)[1]
        with open(filepath,"r") as f:
            first=f.readline()
        if first.startswith(("##!","///!")):
            cmd=first.removeprefix("##!").removeprefix("///!").strip()
        elif first.startswith(("#!","//!")):
            cmd=first.removeprefix("#!").removeprefix("//!").strip() + " $IN"
        else:
            cmd=os.environ.get(f"LIBIMPORTX_DEFAULT_CMD_{ext.upper()}",\
                               EXTENSION_TABLE.get(ext,"$IN"))
    abspath=os.path.abspath(filepath)
    tmpout=os.path.join(tempdir,"out.bin" if os.name!="nt" else "out.exe")
    if os.name!="nt":
        cmd=cmd.replace("$IN",shlex.quote(abspath))\
            .replace("$OUT",shlex.quote(tmpout))
    else:
        cmd=cmd.replace("$IN",f'"{abspath}"').replace("$OUT",f'"{tmpout}"')
    try:
        server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        server.bind(sockpath)
        server.listen(1)
    except Exception as e:
        shutil.rmtree(tempdir)
        raise RuntimeError(f"Failed to create socket: {e}")
    envi=os.environ.copy()
    envi.update({
        "LIBIMPORTX":"true",
        "LIBIMPORTX_HOST":sockpath,
        "LIBIMPORTX_TOKEN":token
    })
    try:
        process=subprocess.Popen(cmd,env=envi,shell=True)
    except Exception as e:
        server.close()
        shutil.rmtree(tempdir)
        raise RuntimeError(f"Failed to start process: {e}")
    server.settimeout(10)
    try:
        conn,_addr=server.accept()
        line,lo=recvLine(conn,b"")
        if not line:
            raise RuntimeError("Process closed connection before sending token")
        if line.decode().strip()!=token:
            conn.sendall(b"-\n")
            conn.close()
            raise PermissionError("Process sent invalid token")
        #else:
        conn.sendall(b"+\n")
        server.settimeout(None) #the user may call a function that takes 11s
        return ImportxModule(conn,process,tempdir=tempdir)
    except socket.timeout:
        process.terminate()
        server.close()
        shutil.rmtree(tempdir)
        raise TimeoutError("Process did not connect within timeout")

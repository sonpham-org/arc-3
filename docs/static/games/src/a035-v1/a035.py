"""a035 Ring Buffer -- preserve bounded overwrite order while rotating an output gate."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RACK,SLOT,TILE,HEAD,EVICT,OUTPUT,GOAL,BAD=4,10,8,14,11,12,6,13,15
LEVELS=[{"name":"First Write","seq":(1,)},{"name":"Rotate Head","seq":(2,1)},{"name":"Read Gate","seq":(3,1,2)},{"name":"Overwrite Oldest","seq":(4,2,1,3)},{"name":"Bounded Stream","seq":(2,3,1,4,2,1)},{"name":"Ring Buffer","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 buffer,head,next_tile,output,evictions,stream=s;b=list(buffer);out=list(output);ev=list(evictions)
 if a==1:
  if len(b)<6:b.append(next_tile)
  else:ev.append(b[head]);b[head]=next_tile;head=(head+1)%6
  next_tile=(next_tile+1)%8
 elif a==2:head=(head+1)%max(1,len(b))
 elif a==3:
  if b:out.append(b[head%len(b)])
 elif a==4:
  for _ in range(2):
   if len(b)<6:b.append(next_tile)
   else:ev.append(b[head]);b[head]=next_tile;head=(head+1)%6
   next_tile=(next_tile+1)%8
 elif a==5:stream=(tuple(b),head,next_tile,tuple(out[-5:]),tuple(ev[-4:]))
 return tuple(b),head,next_tile,tuple(out),tuple(ev),stream
for x in LEVELS:
 s=((),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RACK;coords=[(26,8),(39,14),(39,28),(26,34),(13,28),(13,14)]
  f[1:4,8:28]=TILE;f[1:4,32:52]=HEAD
  for i,(x,y) in enumerate(coords):f[y:y+10,x:x+10]=SLOT;f[y+2:y+8,x+2:x+8]=HEAD if i==g.head and g.buffer else TILE if i<len(g.buffer) else SLOT
  for i,v in enumerate(g.output[-4:]):f[47:53,8+i*12:17+i*12]=OUTPUT
  for i,v in enumerate(g.evictions[-3:]):f[55:59,8+i*14:18+i*14]=EVICT
  if g.stream:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A035(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a035",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buffer=();self.head=self.next_tile=0;self.output=self.evictions=();self.stream=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.buffer,self.head,self.next_tile,self.output,self.evictions,self.stream=advance((self.buffer,self.head,self.next_tile,self.output,self.evictions,self.stream),a)
  elif a==6:
   if (self.buffer,self.head,self.next_tile,self.output,self.evictions,self.stream)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

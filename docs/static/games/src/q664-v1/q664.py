"""q664 Moraine Analogy -- transfer a crevasse relation into one outer dependency slot."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,SOURCE,CREVASSE,TARGET,RAFT,SURFACE,OUTER,GOAL,BAD=5,11,12,10,14,6,7,9,13,15
LEVELS=[
 {"name":"Rotated Crack","path":(0,1,2),"ops":(1,),"surface":0},
 {"name":"Changed Surface","path":(0,2,1),"ops":(2,),"surface":1},
 {"name":"Two Transforms","path":(1,0,2),"ops":(1,2),"surface":1},
 {"name":"Outer Analogy","path":(2,0,1),"ops":(1,1,2),"surface":2},
 {"name":"Nested Transfer","path":(1,2,0),"ops":(2,1,2,2),"surface":2},
 {"name":"Moraine Analogy","path":(0,2,1),"ops":(1,2,1,1,2),"surface":1}]
def advance(s,a):
 path,twist,surface,mapped,outer,done=s;path=list(path);outer=list(outer)
 if a==1:path=path[1:]+path[:1];twist=(twist+1)%3
 elif a==2:path=[2-v for v in reversed(path)];twist^=1
 elif a==3:mapped=tuple((path[i+1]-path[i])%3 for i in range(2));outer[surface]=(sum(mapped)+twist)%4
 elif a==4:surface=(surface+1)%3
 elif a==5:
  if mapped is None:return None
  done=(mapped,surface,tuple(outer))
 return tuple(path),twist,surface,mapped,tuple(outer),done
for x in LEVELS:x["plan"]=x["ops"]+(4,)*x["surface"]+(3,5)
def target(x):
 s=(x["path"],0,0,None,(0,0,0),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ICE;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  for i,v in enumerate(g.path):f[12+i*7,10+v*6:16+v*6]=CREVASSE;f[12+i*7,38+v*6:44+v*6]=RAFT if g.mapped else SURFACE
  f[39:43,8:8+g.twist*15+10]=CREVASSE
  for i,v in enumerate(g.outer):f[48:52,8+i*16:8+i*16+v*3+4]=OUTER
  if g.done:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q664(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q664",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.path=self.cfg["path"];self.twist=self.surface=0;self.mapped=None;self.outer=(0,0,0);self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.path,self.twist,self.surface,self.mapped,self.outer,self.done),a)
   if s is None:self.bad=True;self.lose()
   else:self.path,self.twist,self.surface,self.mapped,self.outer,self.done=s
  elif a==6:
   if (self.path,self.twist,self.surface,self.mapped,self.outer,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

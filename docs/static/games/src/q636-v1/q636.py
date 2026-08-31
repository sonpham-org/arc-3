"""q636 Backstage Sandbox -- retain signed simulation evidence after physical values reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,SIM0,SIM1,POSITIVE,NEGATIVE,RESET,COMMIT,BAD=4,13,10,14,11,9,6,12,15
LEVELS=[
 {"name":"One Reset","tests":(1,1,2),"resets":1},{"name":"Opposed Copies","tests":(2,2,1),"resets":1},
 {"name":"Persistent Direction","tests":(1,2,1,1),"resets":2},{"name":"Signed Sandbox","tests":(2,1,2,2),"resets":3},
 {"name":"Many Pressures","tests":(1,1,2,1,2),"resets":4},{"name":"Backstage Sandbox","tests":(2,1,2,2,1,2),"resets":5}]
def evidence_for(tests):
 e=[0,0]
 for a in tests:e[a-1]+=2 if a==1 else -1
 return tuple(e)
for x in LEVELS:
 e=evidence_for(x["tests"]);x["choice"]=int(e[0]+e[1]<0);x["plan"]=x["tests"]+(3,)*x["resets"]+(4+x["choice"],)
def advance(s,a,x):
 sims,evidence,resets,committed=s;sims=list(sims);evidence=list(evidence)
 if a in (1,2):i=a-1;delta=2 if i==0 else -1;sims[i]+=delta;evidence[i]=sims[i]
 elif a==3:sims=[0,0];resets+=1
 elif a in (4,5):
  choice=a-4;correct=int(sum(evidence)<0)
  if resets<x["resets"] or choice!=correct:return None
  committed=(choice,tuple(evidence))
 return tuple(sims),tuple(evidence),resets,committed
def target(x):
 s=((0,0),(0,0),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:33,8:29]=SIM0;f[8:33,35:56]=SIM1;f[36:38,8:28]=POSITIVE;f[36:38,36:56]=NEGATIVE
  for i,v in enumerate(g.evidence):f[40+i*7:44+i*7,8:8+abs(v)*7]=POSITIVE if v>=0 else NEGATIVE
  f[54:58,8:8+min(g.resets,6)*8]=RESET
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q636(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q636",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=(0,0);self.resets=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.resets,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.resets,self.committed=s
  elif a==6:
   if (self.sims,self.evidence,self.resets,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

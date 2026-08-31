"""q639 Reedbed Sandbox -- retain evidence while simulated components and links reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SIM0,SIM1,EVIDENCE,LINK,RESET,COMMIT,BAD=4,10,9,12,14,11,6,13,15
LEVELS=[
 {"name":"One Copy","tests":(1,1,2),"resets":1},{"name":"Opposed Copies","tests":(2,2,1),"resets":1},
 {"name":"Persistent Evidence","tests":(1,2,1,1),"resets":2},{"name":"Rewired Sandbox","tests":(2,1,2,2),"resets":3},
 {"name":"Many Components","tests":(1,1,2,1,2),"resets":4},{"name":"Reedbed Sandbox","tests":(2,1,2,2,1,2),"resets":5}]
for x in LEVELS:
 score=sum(1 if a==1 else -1 for a in x["tests"]);x["choice"]=0 if score>0 else 1;x["plan"]=x["tests"]+(3,)*x["resets"]+(4+x["choice"],)
def advance(s,a,x):
 sims,simlinks,evidence,resets,mainlinks,committed=s;sims=list(sims);simlinks=list(simlinks)
 if a in (1,2):
  i=a-1;sims[i]+=1;simlinks[i]^=1<<((sims[i]-1)%4);evidence+=(1 if i==0 else -1)*(1+simlinks[i].bit_count()%2)
 elif a==3:sims=[0,0];simlinks=[0,0];resets+=1
 elif a in (4,5):
  choice=a-4;correct=0 if evidence>0 else 1
  if not evidence or resets<x["resets"] or choice!=correct:return None
  mainlinks=(1<<choice)|(1<<(choice+2));committed=(choice,evidence)
 return tuple(sims),tuple(simlinks),evidence,resets,mainlinks,committed
def target(x):
 s=((0,0),(0,0),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:33,8:29]=SIM0;f[8:33,35:56]=SIM1
  for i in range(2):f[12:29,11+i*27:11+i*27+g.simlinks[i].bit_count()*4]=LINK
  f[36:38,8:56]=EVIDENCE;f[38:42,8:8+min(abs(g.evidence),9)*5]=EVIDENCE;f[47:51,8:8+min(g.resets,6)*8]=RESET
  if g.mainlinks:f[54:58,8:8+g.mainlinks.bit_count()*12]=LINK
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q639(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q639",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.simlinks=(0,0);self.evidence=self.resets=self.mainlinks=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.simlinks,self.evidence,self.resets,self.mainlinks,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.simlinks,self.evidence,self.resets,self.mainlinks,self.committed=s
  elif a==6:
   if (self.sims,self.simlinks,self.evidence,self.resets,self.mainlinks,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

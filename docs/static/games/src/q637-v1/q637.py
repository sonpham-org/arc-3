"""q637 Catalyst Sandbox -- reset physical simulations while retaining observed orientations."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,SIM0,SIM1,MEMORY,RESET,HIDDEN,COMMIT,BAD=4,12,9,14,6,10,13,11,15
LEVELS=[
 {"name":"One Reset","tests":(1,1,2),"resets":1},{"name":"Opposed Copies","tests":(2,2,1),"resets":1},
 {"name":"Persistent Memory","tests":(1,2,1,1),"resets":2},{"name":"Stored Sandbox","tests":(2,1,2,2),"resets":3},
 {"name":"Many Orientations","tests":(1,1,2,1,2),"resets":4},{"name":"Catalyst Sandbox","tests":(2,1,2,2,1,2),"resets":5}]
def choice_for(tests):
 orientation=[0,0];memory=[None,None]
 for a in tests:i=a-1;orientation[i]=(orientation[i]+i+1)%4;memory[i]=orientation[i]
 return (sum(v or 0 for v in memory)+len(tests))%2
for x in LEVELS:x["choice"]=choice_for(x["tests"]);x["plan"]=x["tests"]+(3,)*x["resets"]+(4+x["choice"],)
def advance(s,a,x):
 sims,orientation,memory,resets,visible,committed=s;sims=list(sims);orientation=list(orientation);memory=list(memory)
 if a in (1,2):
  i=a-1;sims[i]+=1;orientation[i]=(orientation[i]+i+1)%4;memory[i]=orientation[i]
 elif a==3:sims=[0,0];orientation=[0,0];resets+=1
 elif a in (4,5):
  choice=a-4;correct=(sum(v or 0 for v in memory)+sum(sims)+len(x["tests"]))%2
  if resets<x["resets"] or None in memory or choice!=correct:return None
  visible=0;committed=(choice,tuple(memory))
 return tuple(sims),tuple(orientation),tuple(memory),resets,visible,committed
def target(x):
 s=((0,0),(0,0),(None,None),0,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY;f[8:33,8:29]=SIM0;f[8:33,35:56]=SIM1
  for i in range(2):f[12:29,11+i*27:11+i*27+g.orientation[i]*4]=MEMORY
  f[38:42,8:56]=MEMORY;f[46:50,8:8+min(g.resets,6)*8]=RESET
  if not g.visible:f[53:57,8:28]=HIDDEN
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q637(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q637",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.orientation=(0,0);self.memory=(None,None);self.resets=0;self.visible=1;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.orientation,self.memory,self.resets,self.visible,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.orientation,self.memory,self.resets,self.visible,self.committed=s
  elif a==6:
   if (self.sims,self.orientation,self.memory,self.resets,self.visible,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

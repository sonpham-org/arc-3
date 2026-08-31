"""q641 Pollen Sandbox -- preserve simulation evidence across a wear-changing reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,SIM0,SIM1,EVIDENCE,RESET,RULE,COMMIT,BAD=3,14,10,12,11,8,6,9,15
LEVELS=[
 {"name":"One Reset","tests":(1,1,2),"resets":1},{"name":"Opposed Copies","tests":(2,2,1),"resets":1},
 {"name":"Double Reset","tests":(1,2,1,1),"resets":2},{"name":"Worn Sandbox","tests":(2,1,2,2),"resets":3},
 {"name":"Persistent Samples","tests":(1,1,2,1,2),"resets":4},{"name":"Pollen Sandbox","tests":(2,1,2,2,1,2),"resets":5}]
for x in LEVELS:
 evidence=sum(1 if a==1 else -1 for a in x["tests"]);rule=1;x["choice"]=0 if -evidence>0 else 1;x["plan"]=x["tests"]+(3,)*x["resets"]+(4+x["choice"],)
def advance(s,a,x):
 sims,evidence,rule,resets,committed=s;sims=list(sims)
 if a in (1,2):sims[a-1]+=1;evidence+=1 if a==1 else -1
 elif a==3:
  sims=[0,0];resets+=1
  if resets==x["resets"]:rule^=1
 elif a in (4,5):
  choice=a-4;score=-evidence if rule else evidence;correct=0 if score>0 else 1
  if not evidence or choice!=correct:return None
  committed=choice
 return tuple(sims),evidence,rule,resets,committed
def target(x):
 s=((0,0),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW;f[8:33,8:29]=SIM0;f[8:33,35:56]=SIM1
  f[12:29,12:12+min(g.sims[0],5)*3]=RESET;f[12:29,39:39+min(g.sims[1],5)*3]=RESET
  f[39:43,8:8+min(abs(g.evidence),8)*6]=EVIDENCE;f[47:51,8:8+min(g.resets,6)*8]=RESET;f[54:58,8:28]=RULE+g.rule
  if g.committed is not None:f[54:59,39:56]=COMMIT+g.committed
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q641(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q641",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.evidence=self.rule=self.resets=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.evidence,self.rule,self.resets,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.evidence,self.rule,self.resets,self.committed=s
  elif a==6:
   if (self.sims,self.evidence,self.rule,self.resets,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q638 Asterism Sandbox -- preserve evidence while miniature star systems reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SIM0,SIM1,STAR,PHASE,EVIDENCE,RESET,GOAL,BAD=4,1,10,11,14,6,12,9,13,15
LEVELS=[
 {"name":"Twin Tests","law":0,"seq":(1,2)},{"name":"Repeated Test","law":1,"seq":(1,1,2)},
 {"name":"Precessed Copies","law":2,"seq":(1,3,2)},{"name":"Evidence Reset","law":1,"seq":(1,2,4,1,2)},
 {"name":"Counterfactual Orbit","law":2,"seq":(2,3,1,4,2,1)},
 {"name":"Asterism Sandbox","law":0,"seq":(1,3,2,2,4,2,3,1,1)}]
def advance(s,a,x):
 sims,phase,evidence,committed=s;sims=list(sims)
 if a in (1,2):
  i=a-1;reading=(x["law"]+phase+i+sims[i])%3;sims[i]+=1;evidence=evidence+((i,reading),)
 elif a==3:sims.reverse();phase=(phase+1)%3
 elif a==4:sims=[0,0];phase=0
 elif a==5:
  if {i for i,_ in evidence}!={0,1}:return None
  committed=(x["law"],len(evidence),tuple(sims),phase)
 return tuple(sims),phase,evidence,committed
for x in LEVELS:
 s=((0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((0,0),0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,c in enumerate((SIM0,SIM1)):
   x=8+i*27;f[9:32,x:x+21]=c
   for n in range(3):f[13+n*6:16+n*6,x+4+(n+g.phase)%3*5:x+7+(n+g.phase)%3*5]=STAR
   f[34:38,x:x+min(g.sims[i],5)*4]=RESET
  for j,(i,v) in enumerate(g.evidence[-6:]):f[44:49,8+j*8:14+j*8]=EVIDENCE if (i+v)%2 else PHASE
  f[52:56,8:8+g.phase*14+8]=PHASE
  if g.committed:f[54:59,42:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q638(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q638",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.phase=0;self.evidence=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.phase,self.evidence,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.phase,self.evidence,self.committed=s
  elif a==6:
   if (self.sims,self.phase,self.evidence,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

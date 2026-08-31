"""q643 Impeller Sandbox -- preserve sampled evidence while miniature turbines reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,TURB0,TURB1,BLADE,WAKE,EVIDENCE,RESET,COST,GOAL,BAD=4,1,10,11,14,6,12,9,7,13,15
LEVELS=[
 {"name":"Twin Turbines","seq":(1,2)},{"name":"Repeated Probe","seq":(1,1,2)},
 {"name":"Reversed Copies","seq":(1,3,2)},{"name":"Persistent Evidence","seq":(1,2,4,2,1)},
 {"name":"Costed Sandbox","seq":(2,3,1,1,4,2,1)},
 {"name":"Impeller Sandbox","seq":(1,3,2,2,4,2,3,1,1)}]
def advance(s,a):
 sims,wake,evidence,cost,committed=s;sims=list(sims)
 if a in (1,2):
  i=a-1;decisive={j for j,_ in evidence}=={0,1};reading=(i+wake+sims[i])%3;sims[i]+=1;evidence=evidence+((i,reading),);cost+=2 if decisive else 1
 elif a==3:sims.reverse();wake=(wake+1)%3
 elif a==4:sims=[0,0];wake=0
 elif a==5:
  if {i for i,_ in evidence}!={0,1}:return None
  committed=(tuple(sims),wake,len(evidence),cost,sum(v for _,v in evidence)%4)
 return tuple(sims),wake,evidence,cost,committed
for x in LEVELS:
 s=((0,0),0,(),0,None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((0,0),0,(),0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,c in enumerate((TURB0,TURB1)):
   x=8+i*27;f[8:33,x:x+21]=c
   for n in range(8):xx=x+3+(n%4)*4;yy=11+(n//4)*10;f[yy:yy+6,xx:xx+3]=BLADE if (n+g.wake)%2 else WAKE
   f[35:39,x:x+min(g.sims[i],5)*4]=RESET
  for j,(i,v) in enumerate(g.evidence[-6:]):f[44:49,8+j*8:14+j*8]=EVIDENCE if i else BLADE
  f[52:56,8:8+g.wake*15+10]=WAKE;f[56:60,8:8+min(g.cost,9)*5]=COST
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q643(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q643",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.wake=0;self.evidence=();self.cost=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.wake,self.evidence,self.cost,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.wake,self.evidence,self.cost,self.committed=s
  elif a==6:
   if (self.sims,self.wake,self.evidence,self.cost,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q646 Crossing Sandbox -- alternate marked simulation views while physical ferry copies reset."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SIM0,SIM1,FERRY,DOCK,EVIDENCE,MARK0,MARK1,GOAL,BAD=4,10,11,14,12,6,9,7,5,13,15
LEVELS=[
 {"name":"Twin Views","seq":(1,4,3,1,4)},{"name":"Reset Copy","seq":(1,2,1,4,3,1,4)},
 {"name":"Marked Tests","seq":(1,1,4,3,1,4)},{"name":"Persistent Evidence","seq":(1,2,4,3,1,2,1,4)},
 {"name":"Alternating Sandbox","seq":(1,4,3,1,1,4,3,2,1,4)},
 {"name":"Crossing Sandbox","seq":(1,2,1,4,3,1,4,3,1,2,1,4)}]
def advance(s,a):
 sims,controller,evidence,marks,committed=s;sims=list(sims)
 if a==1:reading=(controller+sims[controller])%4;sims[controller]+=1;evidence=evidence+((controller,reading),)
 elif a==2:sims[controller]=0
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,sims[controller],len(evidence)),)
 elif a==5:
  if {m[0] for m in marks}!={0,1}:return None
  committed=(tuple(sims),controller,len(evidence),marks[-2:])
 return tuple(sims),controller,evidence,marks,committed
for x in LEVELS:
 s=((0,0),0,(),(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((0,0),0,(),(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i,c in enumerate((SIM0,SIM1)):
   x=8+i*27;f[8:32,x:x+21]=c;f[12:28,x+4:x+17]=FERRY if i==g.controller else DOCK;f[34:38,x:x+min(g.sims[i],5)*4]=EVIDENCE
  for i,m in enumerate(g.marks[-5:]):f[44:49,8+i*10:15+i*10]=MARK0 if m[0]==0 else MARK1
  for i,e in enumerate(g.evidence[-5:]):f[52:56,8+i*10:15+i*10]=EVIDENCE if e[0] else FERRY
  if g.committed:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q646(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q646",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.controller=0;self.evidence=();self.marks=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.controller,self.evidence,self.marks,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.controller,self.evidence,self.marks,self.committed=s
  elif a==6:
   if (self.sims,self.controller,self.evidence,self.marks,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

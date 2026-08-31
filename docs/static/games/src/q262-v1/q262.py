"""q262 Tide Probe -- gather causal evidence before one irreversible repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,CURRENT,SHELL,PROBE,EVIDENCE,CHOICE,SEAL,BAD=2,9,10,14,5,11,7,15,8
LEVELS=[{"name":"Direct Current","model":1,"tests":(1,),"budget":1},{"name":"Shared Tide","model":2,"tests":(2,1),"budget":2},{"name":"Coincident Shell","model":3,"tests":(1,3,2),"budget":3},{"name":"Reverse Probe","model":2,"tests":(3,1,2),"budget":3},{"name":"Repair Evidence","model":3,"tests":(2,3,1),"budget":3},{"name":"Tide Probe","model":1,"tests":(1,2,3,1),"budget":4}]
def result(model,a,current):return (model*a+current+1)%4
def advance(s,a,x):
 evidence,choice,current,committed=s;evidence=list(evidence)
 if committed:return None
 if a in (1,2,3):evidence.append((a,current,result(x["model"],a,current)))
 elif a==4:choice=(choice+1)%4;current=1-current
 elif a==5:committed=(choice,tuple(evidence),current)
 return tuple(evidence),choice,current,committed
def target(x):
 s=((),0,0,None)
 for a in x["tests"]:s=advance(s,a,x)
 for _ in range(x["model"]):s=advance(s,4,x)
 return advance(s,5,x)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:15,8:56]=CURRENT
  for i in range(3):x=9+i*18;f[20:34,x:x+12]=SHELL-i;f[24:30,x+4:x+8]=PROBE
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[38+i*3:40+i*3,8:11+v*11]=EVIDENCE
  f[54:57,8:11+g.choice*12]=CHOICE;f[58:60,8:20]=SEAL if g.committed else PROBE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q262(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q262",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.choice=self.current=0;self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.choice,self.current,self.committed),a,x)
   if s is None or (a in (1,2,3) and len(self.evidence)>=x["budget"]):self.bad=True;self.lose()
   else:self.evidence,self.choice,self.current,self.committed=s
  elif a==6:
   if (self.evidence,self.choice,self.current,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

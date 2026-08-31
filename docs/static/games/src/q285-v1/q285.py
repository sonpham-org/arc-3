"""q285 Vivarium Probe -- manage partner favor while diagnosing before irreversible repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HABITAT,STRATUM,FAUNA,PROBE,EVIDENCE,FAVOR,REPAIR,BAD=13,10,9,14,6,4,2,11,15
LEVELS=[{"name":"Direct Fauna","model":1,"budget":1,"plan":(1,4,5)},{"name":"Shared Stratum","model":2,"budget":2,"plan":(2,1,4,4,5)},{"name":"Coincident Colony","model":3,"budget":3,"plan":(1,3,2,4,4,4,5)},{"name":"Reciprocal Probe","model":2,"budget":3,"plan":(3,4,1,2,4,5)},{"name":"Fair Repair","model":3,"budget":3,"plan":(2,1,4,3,4,4,5)},{"name":"Vivarium Probe","model":1,"budget":4,"plan":(1,4,2,3,1,5)}]
def result(model,a,favor):return (model*a+favor+1)%4
def advance(s,a,x):
 evidence,favor,choice,committed=s;evidence=list(evidence)
 if committed:return None
 if a in (1,2,3):evidence.append((a,favor,result(x["model"],a,favor)))
 elif a==4:favor=(favor+(1 if len(evidence)%2 else 3))%4;choice=(choice+1)%4
 elif a==5:committed=(choice,tuple(evidence),favor)
 return tuple(evidence),favor,choice,committed
def target(x):
 s=((),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HABITAT
  for i in range(3):x=9+i*18;f[9:34,x:x+12]=STRATUM;f[15+i*5:22+i*5,x+4:x+8]=FAUNA-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[38+i*3:40+i*3,8:11+v*11]=EVIDENCE
  f[54:57,8:11+g.favor*11]=FAVOR;f[58:60,8:20]=REPAIR if g.committed else PROBE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q285(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q285",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.favor=self.choice=0;self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.evidence,self.favor,self.choice,self.committed),a,x)
   if s is None or (a in (1,2,3) and len(self.evidence)>=x["budget"]):self.bad=True;self.lose()
   else:self.evidence,self.favor,self.choice,self.committed=s
  elif a==6:
   if (self.evidence,self.favor,self.choice,self.committed)==self.target and self.choice==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

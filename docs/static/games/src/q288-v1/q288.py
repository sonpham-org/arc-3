"""q288 Escapement Probe -- discriminate gear faults before an irreversible repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,PROBE,EVIDENCE,DIAG,REPAIR,BAD=2,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Direct Gear","model":1,"fault":1,"budget":1,"plan":(1,4,5)},{"name":"Shared Weight","model":2,"fault":2,"budget":2,"plan":(2,1,4,5)},{"name":"Coincident Tick","model":3,"fault":3,"budget":3,"plan":(1,3,4,2,5)},{"name":"Exclusive Outcome","model":2,"fault":1,"budget":3,"plan":(2,4,3,1,5)},{"name":"Fault Repair","model":3,"fault":2,"budget":4,"plan":(3,1,4,2,3,5)},{"name":"Escapement Probe","model":1,"fault":3,"budget":4,"plan":(1,4,3,2,4,1,5)}]
def result(model,a,phase):return (model*a+phase+1)%4
def advance(s,a,x):
 evidence,phase,diagnostic,committed=s;evidence=list(evidence)
 if committed:return None
 if a in (1,2,3):evidence.append((a,phase,result(x["model"],a,phase)))
 elif a==4:diagnostic=(x["fault"],(x["fault"]*2+phase)%4);phase=(phase+1)%4
 elif a==5:committed=(x["model"],x["fault"],tuple(evidence),diagnostic)
 return tuple(evidence),phase,diagnostic,committed
def target(x):
 s=((),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(3):x=8+i*18;f[9:32,x:x+14]=GEAR;f[15+i*4:22+i*4,x+4:x+10]=WEIGHT-i
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[36+i*3:38+i*3,8:11+v*11]=EVIDENCE
  f[53:56,8:20]=DIAG if g.diagnostic else PROBE;f[57:60,8:20]=REPAIR if g.committed else GEAR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q288(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q288",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.evidence=();self.phase=0;self.diagnostic=self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   probes=len(self.evidence);s=advance((self.evidence,self.phase,self.diagnostic,self.committed),a,x)
   if s is None or (a in (1,2,3) and probes>=x["budget"]):self.bad=True;self.lose()
   else:self.evidence,self.phase,self.diagnostic,self.committed=s
  elif a==6:
   if (self.evidence,self.phase,self.diagnostic,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

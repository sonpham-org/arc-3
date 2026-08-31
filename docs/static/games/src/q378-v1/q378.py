"""q378 Escapement Rig -- assemble a clockwork tool, then diagnose the fault it exposes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,PART,RIG,DIAG,ROUTE,BAD=5,10,9,14,6,12,11,7,15
LEVELS=[{"name":"Single Tooth","fault":1,"plan":(1,4,5)},{"name":"Paired Arbor","fault":2,"plan":(2,1,4,5)},{"name":"Offset Driver","fault":3,"plan":(3,2,4,1,5)},{"name":"Composite Jig","fault":1,"plan":(1,3,2,4,5)},{"name":"Rebuilt Gauge","fault":2,"plan":(2,1,4,3,4,5)},{"name":"Escapement Rig","fault":3,"plan":(3,1,2,4,3,1,4,5)}]
def advance(s,a,x):
 parts,rig,phase,diagnostic,route=s;parts=list(parts)
 if a in (1,2,3):parts[a-1]+=1
 elif a==4:
  if not sum(parts):return None
  rig=(sum((i+1)*v for i,v in enumerate(parts))+phase+x["fault"])%7;parts=[0,0,0];phase=(phase+1)%4
 elif a==5:
  if rig is None:return None
  diagnostic=(x["fault"],rig,phase);route=(rig+x["fault"]+phase)%4
 return tuple(parts),rig,phase,diagnostic,route
def target(x):
 s=((0,0,0),None,0,None,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,v in enumerate(g.parts):x=8+i*18;f[9:32,x:x+14]=GEAR;f[26-v*5:28,x+4:x+10]=PART+i
  f[36:43,8:18+(g.rig or 0)*5]=RIG;f[47:50,8:20]=DIAG if g.diagnostic else WEIGHT;f[53:56,8:11+g.route*12]=ROUTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q378(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q378",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.rig=None;self.phase=0;self.diagnostic=None;self.route=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.phase,self.diagnostic,self.route),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.phase,self.diagnostic,self.route=s
  elif a==6:
   if (self.parts,self.rig,self.phase,self.diagnostic,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

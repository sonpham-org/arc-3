"""q473 Ember Dependency -- reuse stored heat across nested vessel prerequisites."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,CLAY,HEAT,VESSEL,SEAL,LAUNCH,RESOURCE,BAD=3,8,6,2,11,4,9,10,15
def make_plan(need,bands):return (1,)*(2*need)+(2,)*((need+1)//2)+(3,)*need+(4,)*bands+(5,)
LEVELS=[
 {"name":"First Vessel","need":1,"bands":1},{"name":"Shared Heat","need":2,"bands":1},
 {"name":"Nested Temper","need":2,"bands":2},{"name":"Three Branches","need":3,"bands":2},
 {"name":"Stable Lower Patterns","need":3,"bands":3},{"name":"Ember Dependency","need":4,"bands":3}]
for x in LEVELS:x["plan"]=make_plan(x["need"],x["bands"]);x["budget"]=len(x["plan"])+2
def advance(s,a,x):
 clay,heat,vessels,seal,resource,launched=s
 if resource<=0 or launched is not None:return None
 resource-=1
 if a==1:clay+=1
 elif a==2:heat+=2
 elif a==3:
  if clay<2 or heat<1:return None
  clay-=2;heat-=1;vessels+=1
 elif a==4:
  if vessels<x["need"] or seal>=x["bands"]:return None
  seal+=1
 elif a==5:
  if seal!=x["bands"]:return None
  launched=(vessels,seal,clay,heat)
 return clay,heat,vessels,seal,resource,launched
def target(x):
 s=(0,0,0,0,x["budget"],None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:24,8:24]=CLAY;f[8:24,40:56]=HEAT
  for i in range(g.vessels):x=8+i*11;f[31:42,x:x+8]=VESSEL
  f[45:49,8:8+g.seal*13]=SEAL;f[52:56,8:8+g.resource*4]=RESOURCE
  f[26:29,8:8+g.clay*4]=CLAY;f[26:29,35:35+g.heat*5]=HEAT
  if g.launched:f[43:59,56:59]=LAUNCH
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q473(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q473",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.clay=self.heat=self.vessels=self.seal=0;self.resource=self.cfg["budget"];self.launched=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.clay,self.heat,self.vessels,self.seal,self.resource,self.launched),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.clay,self.heat,self.vessels,self.seal,self.resource,self.launched=s
  elif a==6:
   if (self.clay,self.heat,self.vessels,self.seal,self.resource,self.launched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

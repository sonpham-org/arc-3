"""q413 Ember Revision -- recalibrate a worn kiln law while every test consumes fuel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,WEAR,RULE,RESOURCE,REPAIR,BAD=2,9,8,14,12,5,11,7,15
LEVELS=[{"name":"Old Heat","fuel":4,"boundary":3,"mode":1,"plan":(1,2,5)},{"name":"Wear Band","fuel":5,"boundary":2,"mode":2,"plan":(2,1,4,5)},{"name":"Delayed Clay","fuel":5,"boundary":2,"mode":3,"plan":(3,2,1,5)},{"name":"Fuel Revision","fuel":6,"boundary":3,"mode":2,"plan":(1,4,2,3,5)},{"name":"Sparse Calibration","fuel":7,"boundary":2,"mode":1,"plan":(2,3,4,1,2,5)},{"name":"Ember Revision","fuel":8,"boundary":3,"mode":3,"plan":(3,1,4,2,3,1,5)}]
def advance(s,a,x):
 vessels,wear,heat,delay,resource,repairs=s;vessels=list(vessels)
 if resource<=0:return None
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:vessels[i]=(vessels[i]+a+heat)%4
  elif rule==2:vessels[i]=3-vessels[i]
  else:delay=(delay+a+i+heat)%4
  wear+=1
 elif a==4:heat=(heat+1)%4
 elif a==5:vessels=[(v+delay+heat)%4 for v in vessels];delay=0;repairs+=1
 resource-=1
 return tuple(vessels),wear,heat,delay,resource,repairs
def target(x):
 s=((0,1,2),0,0,0,x["fuel"],0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:15,8:56]=HEAT
  for i,v in enumerate(g.vessels):x=9+i*18;f[20:37,x:x+12]=VESSEL-i;f[24+v*3:29+v*3,x+3:x+9]=RULE
  f[42:45,8:11+min(g.wear,7)*6]=WEAR;f[49:52,8:11+g.heat*11]=HEAT;f[54:57,8:11+g.resource*4]=RESOURCE;f[58:60,48:56]=REPAIR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q413(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q413",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.vessels=(0,1,2);self.wear=self.heat=self.delay=self.repairs=0;self.resource=x["fuel"]
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.vessels,self.wear,self.heat,self.delay,self.resource,self.repairs),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.vessels,self.wear,self.heat,self.delay,self.resource,self.repairs=s
  elif a==6:
   if (self.vessels,self.wear,self.heat,self.delay,self.resource,self.repairs)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

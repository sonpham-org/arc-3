"""q533 Ember Lesson -- infer a conditional kiln policy while conserving shared effort."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,BAND,CLAY,HEAT,SEEN,RESOURCE,WASTE,BAD=10,9,8,6,2,11,4,13,15
LEVELS=[
 {"name":"Watch Then Carry","plan":(1,2),"budget":4,"demo":(1,5,2)},
 {"name":"Watch Then Fire","plan":(1,3),"budget":4,"demo":(1,5,3)},
 {"name":"Changed Draft","plan":(1,4,2),"budget":5,"demo":(1,5,4,2)},
 {"name":"Conditional Vessel","plan":(1,4,3,2),"budget":6,"demo":(1,5,4,3,2)},
 {"name":"Return Policy","plan":(1,4,2,3,4,2),"budget":8,"demo":(1,5,4,2,3,4,2)},
 {"name":"Ember Lesson","plan":(1,2,4,3,2,4,2),"budget":9,"demo":(1,5,2,4,3,2,4,2)}]
def advance(s,a,x):
 phase,vessel,heat,seen,waste,resource=s
 if resource<=0:return None
 resource-=1
 if a==1:seen|=1<<phase
 elif a==2:vessel=(vessel+phase+1)%5
 elif a==3:heat=(heat+2*phase+1)%7
 elif a==4:phase^=1
 elif a==5:waste+=1
 return phase,vessel,heat,seen,waste,resource
def target(x):
 s=(0,0,0,0,0,x["budget"])
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[3:61,5:59]=KILN;f[7:18,9:55]=BAND
  for i,a in enumerate(g.cfg["demo"]):f[9:15,10+i*5:14+i*5]=(a+5)%16
  f[24:42,9:24]=CLAY;f[24:42,40:55]=HEAT;f[28:38,25:40]=BAND+g.phase
  f[47:51,9:9+g.vessel*8]=CLAY;f[53:57,9:9+g.heat*6]=HEAT;f[59:62,9:9+g.resource*5]=RESOURCE
  if g.seen:f[20:23,9:9+bin(g.seen).count("1")*12]=SEEN
  if g.waste:f[44:47,45:55]=WASTE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q533(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q533",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=self.vessel=self.heat=self.seen=self.waste=0;self.resource=self.cfg["budget"]
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.phase,self.vessel,self.heat,self.seen,self.waste,self.resource),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.phase,self.vessel,self.heat,self.seen,self.waste,self.resource=s
  elif a==6:
   if (self.phase,self.vessel,self.heat,self.seen,self.waste,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

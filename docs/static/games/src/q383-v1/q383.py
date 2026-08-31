"""q383 Ember Delegation -- integrate disjoint kiln views before shared fuel expires."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,VIEW,MARK,RESOURCE,INTEGRATE,BAD=1,9,8,14,12,5,11,7,15
LEVELS=[{"name":"Split Heat","fuel":7,"plan":(1,3,4,2,3,5)},{"name":"Remote Vessel","fuel":7,"plan":(2,3,4,1,3,5)},{"name":"Alternating Marks","fuel":8,"plan":(1,2,3,4,2,3,5)},{"name":"Fuel Handoff","fuel":9,"plan":(2,1,3,4,1,2,3,5)},{"name":"Sparse Relay","fuel":11,"plan":(1,3,4,2,1,3,4,2,3,5)},{"name":"Ember Delegation","fuel":11,"plan":(2,1,3,4,1,3,4,2,3,5)}]
def advance(s,a):
 controller,views,marks,heat,resource,integrated=s;views=list(views);marks=list(marks)
 if resource<=0:return None
 if a in (1,2):views[controller]|=1<<((controller+a+heat)%4)
 elif a==3:marks[controller]=(views[controller]*3+heat+controller+1)%8
 elif a==4:controller=1-controller;heat=(heat+1)%4
 elif a==5:integrated=(marks[0]^marks[1]^heat)%8
 resource-=1
 return controller,tuple(views),tuple(marks),heat,resource,integrated
def target(x):
 s=(0,(0,0),(0,0),0,x["fuel"],0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:15,8:56]=HEAT
  for i,v in enumerate(g.views):x=7+i*28;f[20:39,x:x+22]=VESSEL-i;f[24:31,x+4:x+4+max(1,v)*3]=VIEW;f[42:45,x:x+max(1,g.marks[i])*3]=MARK
  f[50:53,8:11+g.controller*22]=INTEGRATE;f[55:58,8:11+g.resource*4]=RESOURCE;f[58:60,48:56]=INTEGRATE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q383(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q383",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.controller=0;self.views=(0,0);self.marks=(0,0);self.heat=self.integrated=0;self.resource=x["fuel"]
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.views,self.marks,self.heat,self.resource,self.integrated),a)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.views,self.marks,self.heat,self.resource,self.integrated=s
  elif a==6:
   if (self.controller,self.views,self.marks,self.heat,self.resource,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

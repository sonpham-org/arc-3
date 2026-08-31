"""q547 Catalyst Lesson -- infer a conditional demonstration and execute its stored orientation hidden."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,DEMO,BEAD,CONTEXT,MEMORY,GESTURE,PRODUCT,BAD=1,12,10,14,9,6,13,11,15
LEVELS=[
 {"name":"First Demonstration","rot":1,"switch":0,"gesture":0},{"name":"Context Demonstration","rot":1,"switch":1,"gesture":0},
 {"name":"Empty Gesture","rot":2,"switch":0,"gesture":1},{"name":"Stored Lesson","rot":2,"switch":1,"gesture":1},
 {"name":"Delayed Execution","rot":3,"switch":2,"gesture":2},{"name":"Catalyst Lesson","rot":4,"switch":3,"gesture":2}]
for x in LEVELS:x["plan"]=(1,)*x["rot"]+(2,)+(3,)*x["switch"]+(5,)*x["gesture"]+(4,)
def advance(s,a,x):
 ctx,orientation,memory,visible,gesture,solved=s
 if a==1:orientation=(orientation+1)%4
 elif a==2:memory=(orientation+ctx)%4;visible=1
 elif a==3:ctx^=1
 elif a==4:
  if memory is None:return None
  visible=0;solved=(memory+ctx)%4
 elif a==5:gesture+=1
 return ctx,orientation,memory,visible,gesture,solved
def target(x):
 s=(0,0,None,1,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY;f[8:30,8:56]=DEMO
  for i in range(4):f[11+i*4:14+i*4,11:53]=BEAD if i==g.orientation else CONTEXT+i%2
  f[36:40,8:28]=CONTEXT+g.ctx;f[36:40,36:56]=MEMORY;f[45:49,8:8+(g.memory or 0)*9]=MEMORY
  if g.gesture:f[52:56,8:8+g.gesture*9]=GESTURE
  if g.solved is not None:f[54:59,39:56]=PRODUCT+g.solved
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q547(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q547",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ctx=self.orientation=self.gesture=0;self.memory=self.solved=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ctx,self.orientation,self.memory,self.visible,self.gesture,self.solved),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.ctx,self.orientation,self.memory,self.visible,self.gesture,self.solved=s
  elif a==6:
   if (self.ctx,self.orientation,self.memory,self.visible,self.gesture,self.solved)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

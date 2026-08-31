"""q551 Pollen Lesson -- infer a conditional policy across a visible wear inversion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,BLOOM,POLLEN,CONTEXT,WEAR,RULE,GESTURE,BAD=0,14,11,12,9,13,6,8,15
LEVELS=[
 {"name":"First Bloom","wear":1,"ctx":0,"gesture":0},{"name":"Context Bloom","wear":1,"ctx":1,"gesture":0},
 {"name":"Empty Gesture","wear":2,"ctx":0,"gesture":1},{"name":"Late Complement","wear":3,"ctx":1,"gesture":1},
 {"name":"Long Lesson","wear":4,"ctx":0,"gesture":2},{"name":"Pollen Lesson","wear":5,"ctx":1,"gesture":2}]
for x in LEVELS:x["plan"]=(1,)*x["wear"]+(2,)*x["ctx"]+(5,)*x["gesture"]+(3+(x["ctx"]^1),)
def advance(s,a,x):
 ctx,rule,wear,seen,solved,gesture=s
 if a==1:
  seen=seen+(ctx^rule,);wear+=1
  if wear==x["wear"]:rule^=1
 elif a==2:ctx^=1
 elif a in (3,4):
  choice=a-3
  if not seen or choice!=(ctx^rule):return None
  solved=choice
 elif a==5:gesture+=1
 return ctx,rule,wear,seen,solved,gesture
def target(x):
 s=(0,0,0,(),None,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW;f[8:28,8:56]=BLOOM;f[10:26:6,10:54:8]=POLLEN
  f[33:39,8:28]=CONTEXT+g.ctx;f[33:39,36:56]=RULE+g.rule;f[43:47,8:8+min(g.wear,6)*8]=WEAR
  for i,v in enumerate(g.seen[-5:]):f[51:56,9+i*9:16+i*9]=POLLEN+v
  if g.gesture:f[57:60,8:8+g.gesture*8]=GESTURE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q551(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q551",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ctx=self.rule=self.wear=self.gesture=0;self.seen=();self.solved=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ctx,self.rule,self.wear,self.seen,self.solved,self.gesture),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.ctx,self.rule,self.wear,self.seen,self.solved,self.gesture=s
  elif a==6:
   if (self.ctx,self.rule,self.wear,self.seen,self.solved,self.gesture)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

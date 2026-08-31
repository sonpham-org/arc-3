"""q549 Reedbed Lesson -- infer a policy whose applications also rewire the route."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,DEMO,CONTEXT,LINK,FUNCTION,GESTURE,SOLVED,BAD=1,10,11,9,14,12,6,13,15
LEVELS=[
 {"name":"First Demonstration","shows":1,"ctx":0,"gesture":0},{"name":"Context Switch","shows":1,"ctx":1,"gesture":0},
 {"name":"Ineffective Ripple","shows":2,"ctx":0,"gesture":1},{"name":"Rewired Lesson","shows":3,"ctx":1,"gesture":1},
 {"name":"Conditional Route","shows":4,"ctx":0,"gesture":2},{"name":"Reedbed Lesson","shows":5,"ctx":1,"gesture":2}]
def advance(s,a,x):
 ctx,links,function,seen,gesture,solved=s
 if a==1:
  correct=(ctx+links.bit_count())%2;seen=seen+((ctx,correct),);links^=1<<ctx;function=(function+ctx+1)%5
 elif a==2:ctx^=1
 elif a in (3,4):
  choice=a-3;correct=(ctx+links.bit_count())%2
  if not seen or choice!=correct:return None
  links^=1<<(ctx+2);function=(function+choice+1)%5;solved=(choice,links)
 elif a==5:gesture+=1
 return ctx,links,function,seen,gesture,solved
for x in LEVELS:
 base=(1,)*x["shows"]+(2,)*x["ctx"]+(5,)*x["gesture"];s=(0,0,0,(),0,None)
 for a in base:s=advance(s,a,x);assert s is not None
 x["plan"]=base+(3+((s[0]+s[1].bit_count())%2),)
def target(x):
 s=(0,0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:29,8:56]=DEMO
  for i in range(4):
   x=10+i*11;f[12:25,x:x+7]=LINK if g.links&(1<<i) else CONTEXT+i%2
  f[35:40,8:28]=CONTEXT+g.ctx;f[35:40,36:56]=FUNCTION;f[44:48,8:8+g.function*9]=FUNCTION
  if g.gesture:f[51:55,8:8+g.gesture*9]=GESTURE
  if g.solved:f[56:60,39:56]=SOLVED
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q549(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q549",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ctx=self.links=self.function=self.gesture=0;self.seen=();self.solved=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.ctx,self.links,self.function,self.seen,self.gesture,self.solved),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.ctx,self.links,self.function,self.seen,self.gesture,self.solved=s
  elif a==6:
   if (self.ctx,self.links,self.function,self.seen,self.gesture,self.solved)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

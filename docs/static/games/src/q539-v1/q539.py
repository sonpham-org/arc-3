"""q539 Strata Lesson -- undo a probe physically without erasing what it revealed."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,ORE,PROBE,KNOWLEDGE,CONTEXT,GESTURE,BAD=14,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Probe Then Restore","plan":(1,2,3),"demo":(1,5,2,3)},
 {"name":"Two Faults","plan":(1,1,2,3),"demo":(1,1,5,2,3)},
 {"name":"Changed Stratum","plan":(1,2,4,3),"demo":(1,5,2,4,3)},
 {"name":"Persistent Reading","plan":(1,4,1,2,3),"demo":(1,5,4,1,2,3)},
 {"name":"Conditional Crawler","plan":(1,1,2,4,3,4,3),"demo":(1,1,5,2,4,3,4,3)},
 {"name":"Strata Lesson","plan":(1,4,1,1,2,3,4,3),"demo":(1,5,4,1,1,2,3,4,3)}]
def advance(s,a,x):
 world,knowledge,context,ore,gesture=s
 if a==1:world=(world+1)%4;knowledge|=1<<world
 elif a==2:world=0
 elif a==3:ore=(ore+knowledge.bit_count()+context+1)%7
 elif a==4:context^=1
 elif a==5:gesture+=1
 return world,knowledge,context,ore,gesture
def target(x):
 s=(0,0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(4):f[8+i*9:14+i*9,8:56]=FAULT+i%2
  for i,a in enumerate(g.cfg["demo"]):f[10:14,9+i*5:13+i*5]=(a+5)%16
  f[46:50,8:8+g.world*11]=PROBE;f[52:55,8:8+g.knowledge.bit_count()*10]=KNOWLEDGE;f[56:59,8:12+g.ore*6]=ORE
  f[43:46,44:56]=CONTEXT+g.context
  if g.gesture:f[40:43,8:24]=GESTURE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q539(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q539",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.world=self.knowledge=self.context=self.ore=self.gesture=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.world,self.knowledge,self.context,self.ore,self.gesture=advance((self.world,self.knowledge,self.context,self.ore,self.gesture),a,self.cfg)
  elif a==6:
   if (self.world,self.knowledge,self.context,self.ore,self.gesture)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

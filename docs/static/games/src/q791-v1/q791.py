"""q791 Pollen Rhythm -- interrupt an autonomous routine after its worn period changes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,PULSE,MACRO,BEFORE,AFTER,WEAR,INTERRUPT,BAD=9,14,11,12,10,6,13,8,15
LEVELS=[
 {"name":"First Change","before":3,"after":4,"change":1,"window":1},{"name":"Longer Window","before":3,"after":5,"change":2,"window":2},
 {"name":"Compressed Routine","before":4,"after":3,"change":3,"window":2},{"name":"Worn Rhythm","before":5,"after":4,"change":4,"window":3},
 {"name":"Late Interruption","before":3,"after":6,"change":5,"window":4},{"name":"Pollen Rhythm","before":6,"after":5,"change":6,"window":4}]
for x in LEVELS:x["plan"]=(3,)*x["change"]+(1,)*x["window"]+(4,)
def advance(s,a,x):
 local,macro,period,wear,interrupted=s
 if a==1:local=(local+1)%period
 elif a==2:local=(local+2)%period
 elif a==3:
  macro+=1;local=0;wear+=1
  if wear==x["change"]:period=x["after"]
 elif a==4:
  if wear<x["change"] or local!=x["window"]:return None
  interrupted=(local,macro,period)
 elif a==5:local=0
 return local,macro,period,wear,interrupted
def target(x):
 s=(0,0,x["before"],0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW
  for i in range(6):f[8+i*6:12+i*6,8:56]=BEFORE if i%2==0 else AFTER
  f[11:15,8:8+g.local*8]=PULSE;f[24:28,8:8+(g.macro%6)*8]=MACRO;f[43:47,8:8+g.period*7]=AFTER;f[49:51,8:56]=WEAR;f[51:55,8:8+min(g.wear,6)*8]=WEAR
  if g.interrupted:f[56:60,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q791(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q791",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=self.wear=0;self.period=self.cfg["before"];self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.macro,self.period,self.wear,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.period,self.wear,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.period,self.wear,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q787 Catalyst Rhythm -- store an interruption phase, run macros, then execute it hidden."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PULSE,MACRO,MEMORY,PERIOD,HIDDEN,INTERRUPT,BAD=9,12,10,14,6,11,13,8,15
LEVELS=[
 {"name":"First Window","window":1,"macros":1},{"name":"Second Window","window":2,"macros":1},
 {"name":"Two Routines","window":2,"macros":2},{"name":"Stored Rhythm","window":3,"macros":3},
 {"name":"Long Delay","window":4,"macros":4},{"name":"Catalyst Rhythm","window":5,"macros":5}]
for x in LEVELS:x["plan"]=(1,)*x["window"]+(3,)+(2,)*x["macros"]+(1,)*x["window"]+(4,)
def advance(s,a,x):
 local,macro,period,memory,visible,interrupted=s
 if a==1:local=(local+1)%period
 elif a==2:macro+=1;local=0
 elif a==3:memory=local;visible=1
 elif a==4:
  if memory is None or memory!=x["window"] or local!=memory or macro<x["macros"]:return None
  visible=0;interrupted=(local,macro,memory)
 elif a==5:macro+=2;local=0
 return local,macro,period,memory,visible,interrupted
def target(x):
 s=(0,0,7,None,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY
  for i in range(6):f[8+i*6:12+i*6,8:56]=PULSE if i%2==0 else MACRO
  f[11:15,8:8+g.local*7]=PULSE;f[24:28,8:8+(g.macro%6)*8]=MACRO;f[43:47,8:28]=MEMORY;f[43:47,36:56]=PERIOD
  if not g.visible:f[51:55,8:28]=HIDDEN
  if g.interrupted:f[54:59,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q787(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q787",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=0;self.period=7;self.memory=self.interrupted=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.macro,self.period,self.memory,self.visible,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.period,self.memory,self.visible,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.period,self.memory,self.visible,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q777 Canopy Rhythm -- preserve a capacity-limited store through macro timing."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,TERRACE,SEED,STORE,PULSE,MACRO,INTERRUPT,BAD=10,14,11,12,9,6,13,8,15
LEVELS=[
 {"name":"First Window","capacity":2,"store":1,"routines":1,"window":1},{"name":"Full Store","capacity":2,"store":2,"routines":1,"window":2},
 {"name":"Two Routines","capacity":3,"store":2,"routines":2,"window":2},{"name":"Capacity Rhythm","capacity":3,"store":3,"routines":3,"window":3},
 {"name":"Long Season","capacity":4,"store":3,"routines":4,"window":4},{"name":"Canopy Rhythm","capacity":4,"store":4,"routines":5,"window":5}]
for x in LEVELS:x["plan"]=(1,)*x["store"]+(3,)*x["routines"]+(5,)*x["window"]+(4,)
def advance(s,a,x):
 store,local,macro,interrupted=s
 if a==1:
  if store>=x["capacity"]:return None
  store+=1;local=(local+1)%7
 elif a==2:
  if not store:return None
  store-=1;local=(local+2)%7
 elif a==3:macro+=1;local=0
 elif a==4:
  if store!=x["store"] or macro<x["routines"] or local!=x["window"]:return None
  interrupted=(store,local,macro)
 elif a==5:local=(local+1)%7
 return store,local,macro,interrupted
def target(x):
 s=(0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD
  for i in range(4):f[8+i*8:14+i*8,8:56]=TERRACE+i%2
  f[39:41,8:56]=STORE;f[41:45,8:8+g.store*10]=STORE;f[48:52,8:8+g.local*7]=PULSE;f[55:59,8:8+(g.macro%6)*8]=MACRO
  if g.interrupted:f[54:59,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q777(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q777",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.store=self.local=self.macro=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.store,self.local,self.macro,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.store,self.local,self.macro,self.interrupted=s
  elif a==6:
   if (self.store,self.local,self.macro,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

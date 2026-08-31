"""q775 Alloy Rhythm -- chunk routines and interrupt them in a moving reference frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,LANE,PULSE,LOCAL,MACRO,FRAME,INTERRUPT,BAD=12,1,8,6,2,11,9,4,15
LEVELS=[
 {"name":"Single Interval","cycle":3,"window":1,"outer":0,"plan":(1,5)},
 {"name":"Double Interval","cycle":3,"window":2,"outer":0,"plan":(2,5)},
 {"name":"Whole Routine","cycle":3,"window":0,"outer":1,"plan":(3,5)},
 {"name":"Rotated Window","cycle":4,"window":2,"outer":1,"plan":(3,4,1,5)},
 {"name":"Two Macro Cycles","cycle":5,"window":3,"outer":2,"plan":(3,3,4,2,5)},
 {"name":"Alloy Rhythm","cycle":4,"window":3,"outer":3,"plan":(3,3,3,4,4,1,5)}]
def tick(local,macro,n,cycle):
 total=local+n;wraps=total//cycle;return total%cycle,macro+wraps
def advance(s,a,x):
 local,macro,origin,rotation,interrupted=s
 if a==1:local,macro=tick(local,macro,1,x["cycle"])
 elif a==2:local,macro=tick(local,macro,2,x["cycle"])
 elif a==3:local,macro=tick(local,macro,x["cycle"],x["cycle"])
 elif a==4:origin=(origin+1)%6;rotation=(rotation+1)%x["cycle"]
 elif a==5:
  if (local+rotation)%x["cycle"]!=x["window"] or macro%4!=x["outer"]:return None
  interrupted=(local,macro,origin,rotation)
 return local,macro,origin,rotation,interrupted
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY
  for i in range(4):f[8+i*9:14+i*9,8:56]=LANE+i%2
  f[10:13,8:8+g.local*10]=LOCAL;f[20:23,8:8+(g.macro%4)*10]=MACRO;f[30:33,8:8+g.rotation*9]=PULSE;f[40:43,8:8+g.origin*8]=FRAME
  f[48:51,8:56]=PULSE
  if g.interrupted:f[53:57,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q775(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q775",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=self.origin=self.rotation=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.macro,self.origin,self.rotation,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.origin,self.rotation,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.origin,self.rotation,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q778 Breakwater Rhythm -- a first timing intervention activates after two routines."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,PULSE,LOCAL,MACRO,LATENT,INTERRUPT,BAD=0,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Dormant Offset","cycle":3,"window":1,"outer":2,"plan":(4,3,3,5)},
 {"name":"Second Offset","cycle":3,"window":2,"outer":2,"plan":(4,4,3,3,5)},
 {"name":"Activated Beat","cycle":3,"window":2,"outer":2,"plan":(4,3,3,1,5)},
 {"name":"Shifted Window","cycle":4,"window":3,"outer":2,"plan":(4,4,3,3,1,5)},
 {"name":"Three Routines","cycle":5,"window":3,"outer":3,"plan":(4,3,3,3,2,5)},
 {"name":"Breakwater Rhythm","cycle":4,"window":1,"outer":3,"plan":(4,4,4,3,3,3,2,5)}]
def tick(local,macro,n,cycle):
 total=local+n;return total%cycle,macro+total//cycle
def advance(s,a,x):
 seed,local,macro,active,interrupted=s
 if a==1:local,macro=tick(local,macro,1,x["cycle"])
 elif a==2:local,macro=tick(local,macro,2,x["cycle"])
 elif a==3:local,macro=tick(local,macro,x["cycle"],x["cycle"])
 elif a==4:
  if macro>=2:return None
  seed=(seed+1)%x["cycle"]
 elif a==5:
  if macro<2 or (local+(active if active is not None else seed))%x["cycle"]!=x["window"] or macro%4!=x["outer"]:return None
  interrupted=(seed,local,macro,active)
 if macro>=2:active=seed
 return seed,local,macro,active,interrupted
def target(x):
 s=(0,0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR
  for i in range(4):f[8+i*9:14+i*9,8:56]=CHANNEL+i%2
  f[10:13,8:8+g.local*10]=LOCAL;f[20:23,8:8+(g.macro%4)*10]=MACRO;f[40:43,8:8+g.seed*9]=LATENT;f[47:50,8:56]=PULSE
  if g.interrupted:f[53:57,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q778(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q778",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.seed=self.local=self.macro=0;self.active=self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.seed,self.local,self.macro,self.active,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.seed,self.local,self.macro,self.active,self.interrupted=s
  elif a==6:
   if (self.seed,self.local,self.macro,self.active,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

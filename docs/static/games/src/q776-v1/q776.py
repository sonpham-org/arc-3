"""q776 Palimpsest Rhythm -- retain a failed interruption as timing evidence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,PULSE,LOCAL,MACRO,FAIL,INTERRUPT,BAD=6,8,11,2,4,9,15,13,10
LEVELS=[
 {"name":"Single Beat","cycle":3,"window":1,"outer":0,"need_fail":False,"plan":(1,5)},
 {"name":"Double Beat","cycle":3,"window":2,"outer":0,"need_fail":False,"plan":(2,5)},
 {"name":"Whole Routine","cycle":3,"window":0,"outer":1,"need_fail":False,"plan":(3,5)},
 {"name":"Failed Window","cycle":4,"window":2,"outer":0,"need_fail":True,"plan":(4,2,5)},
 {"name":"Remembered Offset","cycle":5,"window":1,"outer":1,"need_fail":True,"plan":(4,3,1,5)},
 {"name":"Palimpsest Rhythm","cycle":4,"window":3,"outer":2,"need_fail":True,"plan":(4,3,3,2,1,5)}]
def tick(local,macro,n,cycle):
 total=local+n;return total%cycle,macro+total//cycle
def advance(s,a,x):
 local,macro,failure,interrupted=s
 if a==1:local,macro=tick(local,macro,1,x["cycle"])
 elif a==2:local,macro=tick(local,macro,2,x["cycle"])
 elif a==3:local,macro=tick(local,macro,x["cycle"],x["cycle"])
 elif a==4:
  if local==x["window"] and macro%4==x["outer"]:return None
  failure=(local,macro,x["window"],x["outer"])
 elif a==5:
  if local!=x["window"] or macro%4!=x["outer"] or (x["need_fail"] and failure is None):return None
  interrupted=(local,macro,failure)
 return local,macro,failure,interrupted
def target(x):
 s=(0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE
  for i in range(4):f[8+i*9:14+i*9,8:56]=SHELF+i%2
  f[10:13,8:8+g.local*10]=LOCAL;f[20:23,8:8+(g.macro%4)*10]=MACRO;f[42:45,8:56]=PULSE
  if g.failure:f[48:52,8:34]=FAIL
  if g.interrupted:f[54:58,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q776(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q776",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=0;self.failure=self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.macro,self.failure,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.failure,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.failure,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

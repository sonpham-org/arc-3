"""q789 Reedbed Rhythm -- build a period-changing link before interrupting a routine."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,PULSE,MACRO,LINK,PERIOD,FUNCTION,INTERRUPT,BAD=9,10,11,12,14,6,8,13,15
LEVELS=[
 {"name":"First Interrupter","seq":(3,1)},{"name":"Delayed Build","seq":(2,3,1,1)},
 {"name":"Two Links","seq":(3,2,3,1,1,1)},{"name":"Rewired Rhythm","seq":(2,3,2,3,1,1)},
 {"name":"Long Routine","seq":(2,2,3,2,3,1,1,1)},{"name":"Reedbed Rhythm","seq":(3,2,3,2,3,1,1,1,1)}]
def core(s,a,x):
 local,macro,period,links,function,interrupted=s
 if a==1:local=(local+1)%period
 elif a==2:macro+=1;local=0
 elif a==3:links^=1<<(macro%4);period=3+links.bit_count();function=(function+period)%5
 elif a==4:local=0
 elif a==5:
  if local!=x["window"] or links!=x["links"]:return None
  interrupted=(local,macro,period,links)
 return local,macro,period,links,function,interrupted
for x in LEVELS:
 s=(0,0,3,0,0,None)
 for a in x["seq"]:s=core(s,a,x);assert s is not None
 x["window"],x["links"]=s[0],s[3];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,3,0,0,None)
 for a in x["plan"]:s=core(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(6):f[8+i*6:12+i*6,8:56]=PULSE if i%2==0 else MACRO
  f[11:15,8:8+g.local*8]=PULSE;f[24:28,8:8+(g.macro%6)*8]=MACRO;f[43:47,8:8+g.links.bit_count()*12]=LINK;f[51:55,8:8+g.period*7]=PERIOD
  if g.interrupted:f[56:60,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q789(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q789",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=self.links=self.function=0;self.period=3;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=core((self.local,self.macro,self.period,self.links,self.function,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.period,self.links,self.function,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.period,self.links,self.function,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

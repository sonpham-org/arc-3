"""q798 Escapement Rhythm -- diagnose a fault and interrupt nested gear cycles at a phase pair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,TOWER,GEAR,WEIGHT,FAST,SLOW,WINDOW,GOAL,BAD=9,1,12,14,6,10,11,13,15
LEVELS=[
 {"name":"Fast Tick","seq":(1,)},{"name":"Nested Cycle","seq":(1,1,2)},
 {"name":"Fault Pulse","seq":(3,1,2,1)},{"name":"Phase Window","seq":(1,2,1,3,2)},
 {"name":"Macro Interrupt","seq":(2,1,3,1,2,1,1)},
 {"name":"Escapement Rhythm","seq":(1,2,3,1,1,2,1,3,2,1,1)}]
def advance(s,a):
 fast,slow,gear,fault,ticks,interrupted=s
 if a==1:
  fast=(fast+1)%4;ticks+=1
  if fast==0:slow=(slow+1)%5
  gear=(gear+1+fault)%6
 elif a==2:
  fast=(fast+2)%4;slow=(slow+1)%5;ticks+=2;gear=(gear+2)%6
 elif a==3:fault=(fault+1)%3;gear=(gear+fault)%6
 elif a==4:fast=slow=gear=0;ticks+=1
 elif a==5:interrupted=(fast,slow,gear,fault,ticks)
 return fast,slow,gear,fault,ticks,interrupted
for x in LEVELS:
 s=(0,0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(12):
   x=7+(i%6)*9;y=9+(i//6)*15;f[y:y+10,x:x+7]=GEAR if i in (g.fast,g.slow+6) else WEIGHT
  f[41:45,8:8+g.fast*12+8]=FAST;f[48:52,8:8+g.slow*9+7]=SLOW
  f[55:59,8:8+g.gear*7+5]=WINDOW if (g.fast,g.slow)==(g.fault,(g.fault+1)%5) else GEAR
  if g.interrupted:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q798(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q798",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fast=self.slow=self.gear=self.fault=self.ticks=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fast,self.slow,self.gear,self.fault,self.ticks,self.interrupted=advance((self.fast,self.slow,self.gear,self.fault,self.ticks,self.interrupted),a)
  elif a==6:
   if (self.fast,self.slow,self.gear,self.fault,self.ticks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

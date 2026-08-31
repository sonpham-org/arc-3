"""q528 Escapement Frame -- compose weight motion through rotating gears and diagnostic faults."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,FRAME,PROBE,FAULT,GOAL,BAD=0,8,12,14,6,10,11,13,15
LEVELS=[
 {"name":"Local Weight","seq":(1,)},{"name":"Rotated Gear","seq":(2,1)},
 {"name":"Fault Probe","seq":(1,3,2)},{"name":"Translated Phase","seq":(2,1,4,3)},
 {"name":"Exclusive Diagnosis","seq":(1,2,3,4,1,2)},
 {"name":"Escapement Frame","seq":(2,1,4,3,2,1,3,4,1)}]
def advance(s,a):
 weight,gear,rotation,fault,probes,locked=s
 if a==1:weight=(weight+1+rotation+fault)%8;gear=(gear+weight)%6
 elif a==2:rotation=(rotation+1)%4;gear=(gear+rotation)%6
 elif a==3:probes=probes+((weight,gear,(fault+rotation)%3),);fault=(fault+1+gear)%3
 elif a==4:gear=(gear+2+len(probes))%6;weight=(weight+gear)%8
 elif a==5:locked=(weight,gear,rotation,fault,probes[-3:])
 return weight,gear,rotation,fault,probes,locked
for x in LEVELS:
 s=(0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i in range(6):x=8+i*8;f[8:29,x:x+6]=GEAR if i==g.gear else FRAME;f[12+(i%3)*5:17+(i%3)*5,x+2:x+5]=WEIGHT
  for i in range(8):x=8+i*6;f[34:39,x:x+4]=WEIGHT if i==g.weight else FRAME
  for i,p in enumerate(g.probes[-4:]):x=8+i*12;f[44:49,x:x+9]=PROBE;f[50:52,x:x+2+p[2]*2]=FAULT
  f[55:59,8:8+g.rotation*11+7]=FRAME
  if g.locked:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q528(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q528",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.weight=self.gear=self.rotation=self.fault=0;self.probes=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.weight,self.gear,self.rotation,self.fault,self.probes,self.locked=advance((self.weight,self.gear,self.rotation,self.fault,self.probes,self.locked),a)
  elif a==6:
   if (self.weight,self.gear,self.rotation,self.fault,self.probes,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""q338 Survey Drone -- move, rotate, and recharge to collect persistent evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TERRAIN,STATION,DRONE,KNOWN,CHARGE,PHASE,BAD=4,12,11,15,10,14,9,8
MASKS=(0b001101011,0b110010101,0b101110000)
LEVELS=[
 {"name":"First Station","solution":((0,0),),"capacity":1},{"name":"Moving Survey","solution":((0,0),(1,0)),"capacity":1},
 {"name":"Rotated Sensor","solution":((2,1),(0,0)),"capacity":1},{"name":"Dual Charge","solution":((1,0),(2,1),(0,0)),"capacity":2},
 {"name":"Sparse Route","solution":((0,1),(2,0),(1,1)),"capacity":1},{"name":"Survey Drone","solution":((2,1),(1,0),(0,2),(2,0)),"capacity":1}]
def target(x):
 phase=known=0
 for station,rotations in x["solution"]:phase=(phase+rotations)%3;known|=MASKS[(station+phase)%3];phase=(phase+1)%3
 return known
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TERRAIN
  for i in range(3):
   x=9+i*17;f[11:23,x:x+11]=DRONE if i==g.station else STATION
  for i in range(9):
   x=8+(i%3)*17;y=29+(i//3)*6;f[y:y+4,x:x+9]=KNOWN if g.known&(1<<i) else TERRAIN
  f[49:53,8:8+g.charge*13]=CHARGE;f[54:58,8:8+g.phase*15]=PHASE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q338(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.station=self.phase=self.known=0;self.charge=1;self.target=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q338",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.station=self.phase=self.known=0;self.charge=x["capacity"];self.target=target(x);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.station=(self.station-1)%3
  elif a==2:self.station=(self.station+1)%3
  elif a==3:
   if self.charge:self.known|=MASKS[(self.station+self.phase)%3];self.charge-=1
   else:self.bad=True;self.lose()
  elif a==4:self.phase=(self.phase+1)%3
  elif a==5:self.phase=(self.phase+1)%3;self.charge=x["capacity"]
  elif a==6:
   if self.known==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

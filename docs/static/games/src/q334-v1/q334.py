"""q334 Meteor Survey -- allocate remapped telescope passes while evidence persists."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SPACE,METEOR,FILTER,KNOWN,CHARGE,BAD=4,13,12,15,10,14,8
MASKS=(0b001101011,0b110010101,0b101110000)
LEVELS=[
 {"name":"First Meteor","solution":(1,),"capacity":1},{"name":"Turning Orbit","solution":(1,2),"capacity":1},
 {"name":"Remapped Spectrum","solution":(3,1),"capacity":1},{"name":"Dual Pass","solution":(2,3,1),"capacity":2},
 {"name":"Sparse Survey","solution":(1,3,2),"capacity":1},{"name":"Meteor Survey","solution":(3,2,1,3),"capacity":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SPACE
  for i in range(9):
   x=8+(i%3)*17;y=10+(i//3)*13;f[y:y+9,x:x+9]=KNOWN if g.known&(1<<i) else METEOR
  f[49:53,8:8+g.charge*13]=CHARGE;f[54:58,8:8+g.phase*15]=FILTER
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q334(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.selected=self.phase=0;self.charge=1;self.target=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q334",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.known=self.selected=self.phase=0;self.charge=x["capacity"];self.bad=False;phase=0;target=0
  for a in x["solution"]:target|=MASKS[(a-1+phase)%3];phase=(phase+2)%3
  self.target=target
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==4:
   if self.selected and self.charge:self.known|=MASKS[(self.selected-1+self.phase)%3];self.charge-=1;self.selected=0
   else:self.bad=True;self.lose()
  elif a==5:self.phase=(self.phase+2)%3;self.charge=x["capacity"];self.selected=0
  elif a==6:
   if self.known==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

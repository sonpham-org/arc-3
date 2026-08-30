"""q364 Balloon Atelier -- assemble envelopes under coupled pressure and valve state."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ATELIER,PART,BALLOON,PRESSURE,VALVE,BAD=6,10,12,15,9,11,8
LEVELS=[
 {"name":"First Panel","mod":3,"recipe":((1,0,0),)},{"name":"Valve Seam","mod":4,"recipe":((2,1,1),(1,3,0))},
 {"name":"Crosswind Envelope","mod":4,"recipe":((3,2,0),(2,0,1))},{"name":"Reusable Basket","mod":5,"recipe":((1,4,1),(3,2,0),(2,1,1))},
 {"name":"Pressure Workshop","mod":5,"recipe":((2,3,0),(1,0,1),(3,4,1),(2,2,0))},
 {"name":"Balloon Atelier","mod":6,"recipe":((3,5,1),(1,2,0),(2,4,1),(3,1,0),(1,0,1))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=ATELIER
  for i in range(3):
   x=9+i*17;f[11:23,x:x+10]=BALLOON if g.selected==i+1 else PART
  for i in range(len(g.built)):f[30:39,8+i*9:15+i*9]=BALLOON
  f[46:50,8:8+g.pressure*7]=PRESSURE;f[52:57,8:29 if g.valve else 16]=VALVE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q364(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.selected=self.pressure=self.valve=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q364",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.selected=self.pressure=self.valve=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.pressure=(self.pressure+1)%x["mod"]
  elif a==6:self.valve=1-self.valve
  elif a==4:
   i=len(self.built)
   if i<len(x["recipe"]) and (self.selected,self.pressure,self.valve)==x["recipe"][i]:
    self.built.append(self.selected);self.pressure=(self.pressure+self.selected+1)%x["mod"];self.selected=0
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

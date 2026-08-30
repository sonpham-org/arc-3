"""q363 Clockwork Menagerie -- assemble creatures under gear phase and pawl state."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,PART,CREATURE,GEAR,PAWL,BAD=6,12,9,14,11,15,8
LEVELS=[
 {"name":"First Gear","mod":3,"recipe":((1,0,0),)},
 {"name":"Pawl Joint","mod":4,"recipe":((2,1,1),(1,3,0))},
 {"name":"Walking Frame","mod":4,"recipe":((3,2,0),(2,0,1))},
 {"name":"Reusable Chassis","mod":5,"recipe":((1,4,1),(3,2,0),(2,1,1))},
 {"name":"Gear Zoo","mod":5,"recipe":((2,3,0),(1,0,1),(3,4,1),(2,2,0))},
 {"name":"Clockwork Menagerie","mod":6,"recipe":((3,5,1),(1,2,0),(2,4,1),(3,1,0),(1,0,1))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=WORKSHOP
  for i in range(3):
   x=9+i*17;f[11:22,x:x+10]=CREATURE if g.selected==i+1 else PART
  for i in range(len(g.built)):f[29:39,8+i*9:15+i*9]=CREATURE
  f[46:50,8:8+g.phase*7]=GEAR;f[52:57,8:29 if g.pawl else 16]=PAWL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q363(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.selected=self.phase=self.pawl=0;self.built=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q363",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.selected=self.phase=self.pawl=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.phase=(self.phase+1)%x["mod"]
  elif a==6:self.pawl=1-self.pawl
  elif a==4:
   i=len(self.built)
   if i<len(x["recipe"]) and (self.selected,self.phase,self.pawl)==x["recipe"][i]:
    self.built.append(self.selected);self.phase=(self.phase+2*self.selected)%x["mod"];self.selected=0
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q366 Marionette Forge -- assemble figures under phase and latch transitions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FORGE,PART,PUPPET,PHASE,LATCH,BAD=6,12,9,14,11,15,8
LEVELS=[
 {"name":"First Joint","mod":3,"recipe":((1,0,0),)},{"name":"Latched Limb","mod":4,"recipe":((2,1,1),(1,3,0))},
 {"name":"Crossed String","mod":4,"recipe":((3,2,0),(2,0,1))},{"name":"Reusable Frame","mod":5,"recipe":((1,4,1),(3,2,0),(2,1,1))},
 {"name":"Figure Bench","mod":5,"recipe":((2,3,0),(1,0,1),(3,4,1),(2,2,0))},
 {"name":"Marionette Forge","mod":6,"recipe":((3,5,1),(1,2,0),(2,4,1),(3,1,0),(1,0,1))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FORGE
  for i in range(3):
   x=9+i*17;f[11:23,x:x+10]=PUPPET if g.selected==i+1 else PART
  for i in range(len(g.built)):f[30:39,8+i*9:15+i*9]=PUPPET
  f[46:50,8:8+g.phase*7]=PHASE;f[52:57,8:29 if g.latch else 16]=LATCH
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q366(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.selected=self.phase=self.latch=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q366",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.selected=self.phase=self.latch=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.phase=(self.phase+1)%x["mod"]
  elif a==6:self.latch=1-self.latch
  elif a==4:
   i=len(self.built)
   if i<len(x["recipe"]) and (self.selected,self.phase,self.latch)==x["recipe"][i]:
    self.built.append(self.selected);self.phase=(self.phase+2*self.selected+1)%x["mod"];self.latch^=self.selected%2;self.selected=0
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q369 Circuit Weaver -- assemble a circuit while every component rewrites its phase and latch."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BOARD,TRACE,CHIP,PHASE,LATCH,DONE,BAD=6,10,11,14,15,12,13,8
LEVELS=[
 {"name":"First Contact","mod":3,"recipe":((1,0,0),)},
 {"name":"Latched Pair","mod":4,"recipe":((2,1,1),(1,0,1))},
 {"name":"Phase Bridge","mod":5,"recipe":((3,2,0),(2,4,1))},
 {"name":"Crossed Circuit","mod":5,"recipe":((1,4,1),(3,2,0),(2,4,1))},
 {"name":"Feedback Board","mod":6,"recipe":((2,3,0),(1,2,1),(3,5,0),(2,0,1))},
 {"name":"Circuit Weaver","mod":7,"recipe":((3,5,1),(1,5,0),(2,1,1),(3,0,0),(1,0,1))}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=BOARD
  for i,c in enumerate(x["recipe"]):
   y=10+i*8;f[y:y+5,8:19]=DONE if i<len(g.built) else TRACE;f[y+1:y+4,10:10+c[0]*2]=CHIP
  f[12:16,39:39+g.phase*3]=PHASE;f[25:35,42:53]=LATCH if g.latch else BOARD
  f[44:51,39:39+g.selected*4]=CHIP
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q369(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.phase=self.latch=self.selected=0;self.built=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q369",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=self.latch=self.selected=0;self.built=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.selected=a
  elif a==5:self.phase=(self.phase+1)%x["mod"]
  elif a==6:self.latch^=1
  elif a==4:
   need=x["recipe"][len(self.built)] if len(self.built)<len(x["recipe"]) else None
   if need==(self.selected,self.phase,self.latch):
    self.built.append(self.selected);self.phase=(self.phase+2*self.selected+1)%x["mod"];self.latch^=self.selected%2
    if len(self.built)==len(x["recipe"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

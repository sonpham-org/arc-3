"""q422 Lockwater Revision -- identify a worn canal law after carrier exchange."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,WEAR,SWAP,KNOWLEDGE,BAD=2,7,13,10,15,12,6,8
LEVELS=[{"name":n,"rule":r,"boundary":b} for n,r,b in [("Wear Lock",0,1),("Inverted Current",1,2),("Rotated Barge",2,3),("Carrier Exchange",1,4),("Persistent Trail",2,5),("Lockwater Revision",0,6)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CANAL;f[14:27,9:23]=BARGE;f[14:27,41:55]=BARGE;f[31:36,8:56]=WATER;f[42:46,8:8+g.wear*7]=WEAR
  if g.swapped:f[49:53,8:24]=SWAP
  if g.evidence is not None:f[49:54,43:55]=KNOWLEDGE
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q422(ARCBaseGame):
 def __init__(self):self.display=D(self);self.wear=self.candidate=0;self.swapped=False;self.evidence=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q422",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,6])
 def on_set_level(self,l):self.wear=self.candidate=0;self.swapped=False;self.evidence=None;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1 and self.wear<x["boundary"]:self.wear+=1
  elif z==4 and self.wear==x["boundary"]:self.swapped=True
  elif z==2 and self.swapped:self.evidence=x["rule"]
  elif z==3 and self.evidence is not None:self.candidate=(self.candidate+1)%3
  elif z==6:
   if self.swapped and self.evidence==x["rule"] and self.candidate==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

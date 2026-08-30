"""q328 Breakwater Survey -- set-cover sensing with a dormant first observation."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,CHANNEL,SENSOR,EVIDENCE,SUBGOAL,BAD=8,10,12,14,15,13,6,3
LEVELS=[{"name":n,"masks":m,"need":q,"solution":s} for n,m,q,s in [("Channel Slice",[1,2,4,3],7,[1,2,3]),("Cargo Union",[3,6,12,9],15,[1,3]),("Dormant Wake",[5,10,3,12],15,[1,2]),("Two Subgoals",[9,18,36,27],63,[1,2,3]),("Terminal Gate",[7,24,42,49],63,[1,2,4]),("Breakwater Survey",[11,21,38,56],63,[1,3,4])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR;f[13:24,8:22]=SKIFF;f[13:24,42:56]=SKIFF;f[29:34,8:56]=CHANNEL;f[39:44,8:8+g.used*8]=SENSOR;f[47:51,8:8+bin(g.seen).count("1")*7]=EVIDENCE;f[54:57,8:8+g.stage*16]=SUBGOAL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q328(ARCBaseGame):
 def __init__(self):self.display=D(self);self.seen=self.used=self.stage=0;self.first=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q328",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.used=self.stage=0;self.first=None;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and not self.used&(1<<(z-1)):self.seen|=x["masks"][z-1];self.used|=1<<(z-1);self.first=z if self.first is None else self.first
  elif z==5 and self.seen&x["need"]==x["need"] and self.stage<2:self.stage+=1
  elif z==6:
   if self.stage==2 and self.first==x["solution"][0]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q628 Breakwater Sandbox -- persistent miniature evidence with a dormant first effect."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,SKIFF,CHANNEL,SANDBOX,EVIDENCE,SUBGOAL,BAD=8,10,12,14,15,13,6,3
RESP=[[0,1],[1,1],[1,0]]
LEVELS=[{"name":n,"policy":p,"latent":l} for n,p,l in [("Two Harbors",0,0),("Persistent Wake",1,1),("Reset Channel",2,1),("Dormant Gate",1,1),("Two Subgoals",0,0),("Breakwater Sandbox",2,1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR;f[13:27,8:23]=SANDBOX;f[13:27,41:56]=SANDBOX;f[31:36,8:56]=CHANNEL;f[39:44,8:8+g.tested*12]=EVIDENCE;f[49:54,8:8+g.stage*17]=SUBGOAL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q628(ARCBaseGame):
 def __init__(self):self.display=D(self);self.tested=self.physical=self.candidate=self.stage=0;self.first=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q628",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.tested=self.physical=self.candidate=self.stage=0;self.first=None;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2) and not self.physical:self.physical=1;self.tested|=1<<(z-1);r=RESP[x["policy"]][z-1];self.first=r if self.first is None else self.first
  elif z==3 and self.physical:self.physical=0
  elif z==4 and not self.physical:self.candidate=(self.candidate+1)%3
  elif z==5 and not self.physical and self.tested==3 and self.stage<2:self.stage+=1
  elif z==6:
   if not self.physical and self.stage==2 and self.candidate==x["policy"] and self.first==x["latent"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

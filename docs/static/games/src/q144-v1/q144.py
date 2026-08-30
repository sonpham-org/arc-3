"""q144 One Reset -- experiment once, reset progress, then execute with retained evidence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,HIDDEN,EVIDENCE,RESET,PLAYER,DONE,BAD=13,1,3,10,12,9,14,8
LEVELS=[{"name":n,"route":r} for n,r in [("Experiment",[1,4]),("Preserved Evidence",[3,1,4]),("Longer Reset",[2,4,1,3]),("One Chance",[4,1,3,2,4]),("Evidence Split",[1,3,2,4,1,2]),("One Reset",[3,1,4,2,3,4,1])]]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=LAB
  for i,a in enumerate(g.route):x=7+i*7;f[23:32,x:x+5]=DONE if i<g.progress else EVIDENCE if g.evidence else HIDDEN;f[25:28,x:x+a]=PLAYER
  f[40:47,26:38]=RESET if g.reset else HIDDEN
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q144(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=0;self.evidence=False;self.dirty=False;self.reset=True;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q144",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.route=list(LEVELS[self.level_index]["route"]);self.progress=0;self.evidence=self.dirty=False;self.reset=True;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5 and not self.evidence:self.evidence=True;self.dirty=True
  elif a==6 and self.reset and self.dirty:self.progress=0;self.dirty=False;self.reset=False
  elif 1<=a<=4 and self.evidence and not self.dirty:
   if a!=self.route[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.route):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()

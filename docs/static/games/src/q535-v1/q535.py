"""q535 Alloy Lesson -- conditional demonstrations interpreted in a rotating frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,DEMO,FRAME,OUTPUT,BAD=1,7,12,14,15,10,6,8
LEVELS=[{"name":n,"maps":m,"demo":d} for n,m,d in [
 ("Force Example",[[1,2,3,4],[2,1,4,3]],[[1,0,1],[4,0,0],[2,1,1]]),("Rotating Lane",[[2,3,4,1],[4,3,2,1]],[[3,0,1],[1,1,1],[2,1,0],[4,0,1]]),
 ("Conditional Billet",[[3,1,4,2],[2,4,1,3]],[[2,1,1],[4,0,1],[1,0,0],[3,1,1]]),("No-op Gesture",[[4,2,1,3],[3,1,2,4]],[[1,0,1],[2,1,0],[4,1,1],[3,0,1]]),
 ("Delay the Cast",[[2,4,3,1],[1,3,4,2]],[[4,1,1],[3,0,1],[1,1,0],[2,0,1],[1,1,1]]),("Alloy Lesson",[[3,4,1,2],[4,1,3,2]],[[2,0,1],[1,1,1],[4,0,0],[3,1,1],[4,0,1],[1,0,1]])]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[6:58,4:60]=FOUNDRY;f[14:28,8:22]=BILLET;f[14:28,42:56]=BILLET;f[32:37,8:56]=FORCE;f[43:47,8:8+g.observed*7]=DEMO;f[50:53,8:8+g.rotation*12]=FRAME;f[54:57,35:35+len(g.result)*5]=OUTPUT
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q535(ARCBaseGame):
 def __init__(self):self.display=D(self);self.observed=self.rotation=0;self.result=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q535",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.observed=self.rotation=0;self.result=[];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index];valid=[d for d in x["demo"] if d[2]]
  if z==0:self.complete_action();return
  if z==5:self.observed+=self.observed<len(x["demo"])
  elif z in (1,2,3,4) and self.observed==len(x["demo"]) and len(self.result)<len(valid):c=valid[len(self.result)][1];self.result.append(x["maps"][c][(z-1+self.rotation)%4]);self.rotation=(self.rotation+1)%4
  elif z==6:
   if self.result==[d[0] for d in valid]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

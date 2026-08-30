"""q597 Canopy Grammar -- relay transformed grouped commands through a bounded store."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,LEAF,GLIDER,STORE,RELAY,GROUP,BAD=7,11,13,14,12,15,10,8
LEVELS=[{"name":n,"commands":c,"shift":s,"capacity":k} for n,c,s,k in [
 ("Seed Pair",[[1,3]],0,2),("Shade Relay",[[2,4],[1,3]],1,2),("Grouped Route",[[4,2],[3,1]],2,2),
 ("Narrow Store",[[3,4],[1,2],[4,1]],1,2),("Nested Message",[[2,1,4],[3,2],[1,4]],3,3),("Canopy Grammar",[[4,1,2],[2,3],[3,4,1],[1,2]],2,3)]]
def enc(a,shift,group):return((a-1+shift+group)%4)+1
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=ORCHARD;f[13:18,8:56]=LEAF;f[23:31,9:21]=GLIDER
  for i in range(len(g.buffer)):f[35:42,8+i*12:18+i*12]=STORE
  f[47:51,8:56]=RELAY;f[53:57,8:8+g.progress*10]=GROUP
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q597(ARCBaseGame):
 def __init__(self):self.display=D(self);self.buffer=[];self.progress=0;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q597",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5])
 def on_set_level(self,l):self.buffer=[];self.progress=0;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3,4) and len(self.buffer)<x["capacity"]:self.buffer.append(enc(z,x["shift"],self.progress))
  elif z==5:
   if self.buffer==x["commands"][self.progress]:self.progress+=1;self.buffer=[]
   else:self.bad=True;self.lose()
   if self.progress==len(x["commands"]):self.next_level()
  else:self.bad=True;self.lose()
  self.complete_action()

"""q690 Spore Evidence -- weighted stopping at sparse dual-clock events."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,HUMIDITY,SCORE,STORE,CLOCK,BAD=10,2,13,12,15,14,6,8
LEVELS=[{"name":n,"samples":s,"mods":m,"cap":c} for n,s,m,c in [
 ("Weighted Spore",[[0,2],[1,1],[0,2]],[2,3],2),("Sparse Event",[[2,1],[1,2],[1,2],[2,1]],[3,4],2),("Unequal Clocks",[[2,3],[0,1],[1,1],[2,2]],[4,5],2),
 ("Safe Margin",[[0,1],[1,2],[0,3],[2,1]],[5,6],2),("Remaining Wind",[[1,1],[2,3],[1,2],[0,1],[1,3]],[6,7],3),("Spore Evidence",[[2,2],[0,2],[1,1],[2,3],[0,1],[2,2]],[7,8],2)]]
def lead(s):return max(range(3),key=lambda i:s[i])
def safe(s,r):a=sorted(s,reverse=True);return a[0]>a[1]+r
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=GREENHOUSE;f[13:25,8:22]=SPORE;f[13:25,42:56]=SPORE;f[30:35,8:56]=HUMIDITY;f[40:44,8:8+len(g.store)*10]=STORE;f[48:52,8:8+sum(g.scores)*4]=SCORE;f[54:57,8:8+sum(g.phase)*4]=CLOCK
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q690(ARCBaseGame):
 def __init__(self):self.display=D(self);self.phase=[0,0];self.index=self.cursor=0;self.scores=[0,0,0];self.store=[];self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q690",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.phase=[0,0];self.index=self.cursor=0;self.scores=[0,0,0];self.store=[];self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z==1:self.phase[0]=(self.phase[0]+1)%x["mods"][0]
  elif z==2:self.phase[1]=(self.phase[1]+1)%x["mods"][1]
  elif z==3 and self.phase==[0,0] and self.index<len(x["samples"]) and len(self.store)<x["cap"]:self.store.append(x["samples"][self.index]);self.index+=1;self.phase=[1%x["mods"][0],2%x["mods"][1]]
  elif z==4 and self.store:
   for c,w in self.store:self.scores[c]+=w
   self.store=[]
  elif z==5:self.cursor=(self.cursor+1)%3
  elif z==6:
   remain=sum(w for _,w in x["samples"][self.index:])
   if not self.store and safe(self.scores,remain) and self.cursor==lead(self.scores):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

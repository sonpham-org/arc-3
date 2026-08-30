"""q265 Alloy Probe -- diagnose hidden billet links in a rotating frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,PROBE,FRAME,HYPOTHESIS,BAD=1,7,12,14,15,10,6,8
LINKS=[[0,1],[1,1],[1,0]]
LEVELS=[
 {"name":"Direct Lane","model":0,"budget":4},{"name":"Shared Magnet","model":1,"budget":5},
 {"name":"Coincident Billet","model":2,"budget":6},{"name":"Rotating Test","model":1,"budget":5},
 {"name":"Irreversible Repair","model":2,"budget":6},{"name":"Alloy Probe","model":0,"budget":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for x in (9,26,43):f[15:30,x:x+11]=BILLET
  f[34:39,8:56]=FORCE;f[43:48,8:8+g.seen*10]=PROBE;f[51:54,8:8+g.frame*14]=FRAME;f[49:56,43+g.candidate*4:47+g.candidate*4]=HYPOTHESIS
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q265(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.model=self.budget=self.frame=self.seen=self.candidate=0;self.evidence=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q265",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5])
 def on_set_level(self,l):x=LEVELS[self.level_index];self.model=x["model"];self.budget=x["budget"];self.frame=self.seen=self.candidate=0;self.evidence=[];self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if self.budget<0:self.fail()
  elif z in (1,2):self.evidence.append(LINKS[self.model][(z-1+self.frame)%2]);self.seen|=1<<(z-1);self.frame=(self.frame+1)%2
  elif z==3:self.candidate=(self.candidate+1)%3;self.frame=(self.frame+1)%2
  elif z==5:
   if self.seen==3 and self.candidate==self.model:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

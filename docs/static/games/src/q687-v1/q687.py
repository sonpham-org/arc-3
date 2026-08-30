"""q687 Canopy Evidence -- bounded weighted evidence with calibrated early stopping."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,LEAF,WEIGHT,SCORE,STORE,CURSOR,BAD=7,11,13,15,10,14,12,8
LEVELS=[
 {"name":"Weighted Leaves","samples":[[0,2],[1,1],[0,2]],"capacity":2},
 {"name":"Bounded Basket","samples":[[2,1],[1,2],[1,2],[2,1]],"capacity":2},
 {"name":"Remaining Wind","samples":[[2,3],[0,1],[1,1],[2,2]],"capacity":3},
 {"name":"Safe Margin","samples":[[0,1],[1,2],[0,3],[2,1],[0,2]],"capacity":2},
 {"name":"Late Challenger","samples":[[1,1],[2,3],[1,2],[0,1],[1,3]],"capacity":3},
 {"name":"Canopy Evidence","samples":[[2,2],[0,2],[1,1],[2,3],[0,1],[2,2]],"capacity":2}]
def totals(samples):return [sum(w for c,w in samples if c==i) for i in range(3)]
def leader(scores):return max(range(3),key=lambda i:scores[i])
def guaranteed(scores,remaining):
 a=sorted(scores,reverse=True);return a[0]>a[1]+remaining
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,5:59]=ORCHARD
  for i,(c,w) in enumerate(l["samples"]):x=8+i*8;f[10:15,x:x+5]=LEAF if i>=g.index else SCORE;f[8-w:8,x:x+5]=WEIGHT
  for i,s in enumerate(g.scores):f[49-s*2:49,10+i*16:20+i*16]=SCORE
  for i in range(len(g.store)):f[32:37,10+i*8:16+i*8]=STORE
  f[52:57,10+g.cursor*16:20+g.cursor*16]=CURSOR
  if g.bad:f[60:63,22:42]=BAD
  return f
class Q687(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.index=self.cursor=0;self.scores=[0,0,0];self.store=[];self.memory=None;self.stopped=self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q687",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):self.index=self.cursor=0;self.scores=[0,0,0];self.store=[];self.memory=None;self.stopped=self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index]
  if z==1 and self.index<len(l["samples"]) and len(self.store)<l["capacity"]:self.store.append(l["samples"][self.index]);self.index+=1
  elif z==2 and not self.stopped:self.cursor=(self.cursor+1)%3
  elif z==3 and self.store and not self.stopped:
   for c,w in self.store:self.scores[c]+=w
   self.store=[]
  elif z==5 and not self.store and not self.stopped:
   remaining=sum(w for _,w in l["samples"][self.index:])
   if guaranteed(self.scores,remaining) and self.cursor==leader(self.scores):self.memory=self.cursor;self.stopped=True
   else:self.fail()
  elif z==6 and self.stopped:
   if self.memory==leader(totals(l["samples"])):self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()

"""q233 Ember Pact -- infer a hidden social convention under a shared budget."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,VESSEL,HEAT,OFFER,REPLY,CANDIDATE,BAD=3,13,9,14,12,15,6,8
SIG=[[1,1,2],[1,2,1],[2,1,1]]
LEVELS=[
 {"name":"Stored Heat","rule":0,"budget":4},{"name":"Recent Offer","rule":1,"budget":5},
 {"name":"Reciprocal Band","rule":2,"budget":6},{"name":"Fairness Cost","rule":1,"budget":5},
 {"name":"Finite Trust","rule":2,"budget":6},{"name":"Ember Pact","rule":0,"budget":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[6:58,5:59]=KILN
  for i in range(3):x=9+i*17;f[15:29,x:x+11]=VESSEL;f[31:35,x:x+11]=REPLY if g.seen&(1<<i) else OFFER
  f[40:44,8:8+g.budget*7]=HEAT;f[48:54,9+g.candidate*17:20+g.candidate*17]=CANDIDATE
  if g.bad:f[60:63,22:42]=BAD
  return f
class Q233(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.budget=self.seen=self.candidate=0;self.replies=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q233",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):x=LEVELS[self.level_index];self.rule=x["rule"];self.budget=x["budget"];self.seen=self.candidate=0;self.replies=[];self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if self.budget<0:self.fail()
  elif z in (1,2,3):self.seen|=1<<(z-1);self.replies.append(SIG[self.rule][z-1])
  elif z==4:self.candidate=(self.candidate+1)%3
  elif z==5:
   if self.seen&3==3 and self.candidate==self.rule:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
